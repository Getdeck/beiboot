import base64
import logging
import string
import random
from asyncio import sleep
from typing import List, Awaitable

import kubernetes as k8s

from beiboot.configuration import ClusterConfiguration

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


async def check_deployment_ready(
    deployment: k8s.client.V1Deployment, cluster_config: ClusterConfiguration
):
    app = k8s.client.AppsV1Api()
    core_v1_api = k8s.client.CoreV1Api()

    i = 0
    dep = app.read_namespaced_deployment(
        name=deployment.metadata.name, namespace=deployment.metadata.namespace
    )
    # a primitive timeout of configuration.API_SERVER_STARTUP_TIMEOUT in seconds
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
                    for label in list(deployment.spec.selector["matchLabels"].items())
                ]
            )
            api_pod = core_v1_api.list_namespaced_pod(
                deployment.metadata.namespace,
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
            logger.info("Waiting for API Pod to become ready")
            await sleep(1)
        i += 1
        dep = app.read_namespaced_deployment(
            name=deployment.metadata.name, namespace=deployment.metadata.namespace
        )
    # reached this in an error case a) timout (build took too long) or b) build could not be successfully executed
    logger.error("API Pod did not become ready")
    return False


async def get_kubeconfig(
    aw_deployment_ready: Awaitable,
    deployment: k8s.client.V1Deployment,
    cluster_config: ClusterConfiguration,
) -> dict:
    api_ready = await aw_deployment_ready
    if not api_ready:
        # this is a critical error; probably remove the complete cluster
        return {}
    core_v1_api = k8s.client.CoreV1Api()

    selector = ",".join(
        [
            "{0}={1}".format(*label)
            for label in list(deployment.spec.selector["matchLabels"].items())
        ]
    )

    api_pod = core_v1_api.list_namespaced_pod(
        deployment.metadata.namespace, label_selector=selector
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
            deployment.metadata.namespace,
            cluster_config.apiServerContainerName,
            ["cat", cluster_config.kubeconfigFromLocation],
        )
        if "No such file or directory" in kubeconfig:
            await sleep(1)
            i += 1
        else:
            break
    # return a dict with the source generated by the K8s provider
    return {"source": base64.b64encode(kubeconfig.encode("utf-8")).decode("utf-8")}
