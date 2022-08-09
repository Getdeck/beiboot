import base64
import logging
import string
import random
from asyncio import sleep
from typing import List, Awaitable, Optional

import kubernetes as k8s
import yaml

from beiboot.configuration import ClusterConfiguration, BeibootConfiguration

logger = logging.getLogger("beiboot")


def generate_token(length=10) -> str:
    return "".join(
        random.choice(string.ascii_uppercase + string.digits) for _ in range(length)
    )


def exec_command_pod(
    api_instance: k8s.client.CoreV1Api,
    pod_name: str,
    namespace: str,
    container_name: str,
    command: List[str],
    run_async: bool = False,
) -> str:
    """
    Exec a command on a Pod and exit
    :param api_instance: a CoreV1Api instance
    :param pod_name: the name of the Pod to exec this command on
    :param namespace: the namespace this Pod is running in
    :param container_name: the container name of this Pod
    :param command: command as List[str]
    :param run_async: run this command async
    :return: the result output as str
    """
    if run_async:
        resp = api_instance.connect_get_namespaced_pod_exec(
            pod_name,
            namespace,
            container=container_name,
            command=command,
            stderr=False,
            stdin=False,
            stdout=False,
            tty=False,
            async_req=True,
        )
    else:
        resp = k8s.stream.stream(
            api_instance.connect_get_namespaced_pod_exec,
            pod_name,
            namespace,
            container=container_name,
            command=command,
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False,
        )
    if not run_async:
        logger.debug("Response: " + resp)
    return resp


async def check_workload_ready(
    statefulset: k8s.client.V1StatefulSet, cluster_config: ClusterConfiguration
):
    app = k8s.client.AppsV1Api()
    core_v1_api = k8s.client.CoreV1Api()

    i = 0
    dep = app.read_namespaced_stateful_set(
        name=statefulset.metadata.name, namespace=statefulset.metadata.namespace
    )
    # a primitive timeout of configuration.API_SERVER_STARTUP_TIMEOUT in seconds
    logger.info("Waiting for workload to become ready...")
    while i <= cluster_config.clusterReadyTimeout:
        s = dep.status
        if (
            s.updated_replicas == dep.spec.replicas
            and s.replicas == dep.spec.replicas  # noqa
            and s.available_replicas == dep.spec.replicas  # noqa
            and s.observed_generation >= dep.metadata.generation  # noqa
        ):
            selector = ",".join(
                [
                    "{0}={1}".format(*label)
                    for label in list(statefulset.spec.selector["matchLabels"].items())
                ]
            )
            api_pod = core_v1_api.list_namespaced_pod(
                statefulset.metadata.namespace,
                label_selector=selector,
            )
            if len(api_pod.items) != 1:
                logger.warning(
                    f"API pod not yet ready, Pods: {len(api_pod.items)} which is != 1"
                )
                await sleep(1)
                continue
            api_pod_name = api_pod.items[0].metadata.name
            logger.info(f"API Pod ready: {api_pod_name}")
            return True
        else:
            logger.debug("Waiting for API Pod to become ready")
            await sleep(1)
        i += 1
        dep = app.read_namespaced_stateful_set(
            name=statefulset.metadata.name, namespace=statefulset.metadata.namespace
        )
    # reached this in an error case a) timout (build took too long) or b) build could not be successfully executed
    logger.error("API Pod did not become ready")
    return False


async def get_kubeconfig(
    aw_workload_ready: Awaitable,
    statefulset: k8s.client.V1StatefulSet,
    cluster_config: ClusterConfiguration,
    gefyra_endpoint: str = None,
    gefyra_nodeport: int = None,
) -> dict:
    api_ready = await aw_workload_ready
    if not api_ready:
        # this is a critical error; probably remove the complete cluster
        return {}
    core_v1_api = k8s.client.CoreV1Api()

    selector = ",".join(
        [
            "{0}={1}".format(*label)
            for label in list(statefulset.spec.selector["matchLabels"].items())
        ]
    )

    api_pod = core_v1_api.list_namespaced_pod(
        statefulset.metadata.namespace, label_selector=selector
    )
    if len(api_pod.items) != 1:
        logger.warning(f"There is more then one API Pod, it is {len(api_pod.items)}")
    api_pod_name = api_pod.items[0].metadata.name
    # busywait for Kubeconfig to become available
    i = 0
    while i <= cluster_config.clusterReadyTimeout:
        kubeconfig = exec_command_pod(
            core_v1_api,
            api_pod_name,
            statefulset.metadata.namespace,
            cluster_config.apiServerContainerName,
            ["cat", cluster_config.kubeconfigFromLocation],
        )
        if "No such file or directory" in kubeconfig:
            await sleep(1)
            i += 1
        else:
            break
    # return a dict with the source generated by the K8s provider
    # add gefyra connection params to kubeconfig
    if gefyra_endpoint and gefyra_nodeport:
        data = yaml.safe_load(kubeconfig)
        for ctx in data["contexts"]:
            if ctx["name"] == "default":
                ctx["gefyra"] = f"{gefyra_endpoint}:{gefyra_nodeport}"
        kubeconfig = yaml.dump(data)
    return {"source": base64.b64encode(kubeconfig.encode("utf-8")).decode("utf-8")}


def get_external_node_ips(
    api_instance: k8s.client.CoreV1Api, config: BeibootConfiguration
) -> List[Optional[str]]:
    ips = []
    try:
        nodes = api_instance.list_node()
    except Exception as e:  # noqa
        logger.error("Could not read Kubernetes nodes: " + str(e))
        return []

    for node in nodes.items:
        try:
            for address in node.status.addresses:
                if address.type == "ExternalIP":
                    ips.append(str(address.address))
        except Exception as e:  # noqa
            logger.error("Could not read Kubernetes node: " + str(e))
    logger.debug(ips)
    return ips


def get_taken_gefyra_ports(
    api_instance: k8s.client.CustomObjectsApi, config: BeibootConfiguration
) -> List[Optional[int]]:
    try:
        beiboots = api_instance.list_namespaced_custom_object(
            namespace=config.NAMESPACE,
            group="getdeck.dev",
            plural="beiboots",
            version="v1",
        )
    except Exception as e:  # noqa
        logger.error(
            "Could not read Beiboot objects from the cluster due to the following error: "
            + str(e)
        )
        return []
    taken_ports = []
    for beiboot in beiboots.items():
        if hasattr(beiboot, "gefyra"):
            port = beiboot.get("gefyra").get("port")
            try:
                taken_ports.append(int(port))
            except (ValueError, TypeError) as e:
                logger.warning(
                    f"Cannot read Gefyra ports from {beiboot.metadata.name} due to: {e}"
                )
        else:
            continue
    return taken_ports
