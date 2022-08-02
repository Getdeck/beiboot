import base64
import logging
import os
import pathlib
from typing import List, Optional

import docker.errors
import kubernetes as k8s
from beiboot.configuration import ClientConfiguration
from docker.models.containers import Container

logger = logging.getLogger("getdeck.beiboot")


def create_beiboot_custom_ressource(
    config: ClientConfiguration, name: str, ports: List[str]
) -> dict:
    cr = {
        "apiVersion": "getdeck.dev/v1",
        "kind": "beiboot",
        "provider": "k3s",
        "ports": ports,
        "metadata": {
            "name": name,
            "namespace": config.NAMESPACE,
        },
    }
    return cr


def decode_kubeconfig(kubeconfig_obj: dict):
    b64_kubeconfig = kubeconfig_obj["source"]
    kubeconfig = base64.b64decode(b64_kubeconfig.encode("utf-8")).decode("utf-8")
    return kubeconfig


def get_kubeconfig_location(config: ClientConfiguration, cluster_name: str) -> str:
    return config.KUBECONFIG_LOCATION.joinpath(f"{cluster_name}.yaml")


def save_kubeconfig_to_file(
    config: ClientConfiguration, cluster_name: str, kubeconfig
) -> str:
    location = get_kubeconfig_location(config, cluster_name)
    with open(location, "w") as yaml_file:
        yaml_file.write(kubeconfig)
    return location


def delete_kubeconfig_file(config: ClientConfiguration, cluster_name: str):
    location = get_kubeconfig_location(config, cluster_name)
    pathlib.Path(location).unlink(missing_ok=True)


def _get_tooler_container_name(cluster_name: str):
    return f"getdeck-proxy-{cluster_name}"


def start_kubeapi_portforwarding(config: ClientConfiguration, cluster_name: str):
    bbt = config.K8S_CUSTOM_OBJECT_API.get_namespaced_custom_object(
        namespace=config.NAMESPACE,
        name=cluster_name,
        group="getdeck.dev",
        plural="beiboots",
        version="v1",
    )
    forwarded_ports = bbt.get("ports")
    forwards = []
    for idx, port in enumerate(forwarded_ports):
        forwards.append(
            (
                port.split(":")[0],
                [
                    "kubectl",
                    "port-forward",
                    "-n",
                    bbt["beibootNamespace"],
                    f"svc/port-{port.split(':')[1]}",
                    port,
                    "--address='0.0.0.0'",
                ],
            )
        )

    forwards.append(
        (
            config.BEIBOOT_API_PORT,
            [
                "kubectl",
                "port-forward",
                "-n",
                bbt["beibootNamespace"],
                "svc/kubeapi",
                f"{config.BEIBOOT_API_PORT}:{config.BEIBOOT_API_PORT}",
                "--address='0.0.0.0'",
            ],
        )
    )
    if config.KUBECONFIG_FILE:
        kubeconfig_path = config.KUBECONFIG_FILE
    else:
        from kubernetes.config import kube_config

        kubeconfig_path = os.path.expanduser(kube_config.KUBE_CONFIG_DEFAULT_LOCATION)
    for forward in forwards:
        try:
            _cmd = ["/bin/sh", "-c", f"{' '.join(forward[1])}"]
            logger.debug(_cmd)
            container = config.DOCKER.containers.run(  # noqa
                image=config.TOOLER_IMAGE,
                name=f"{_get_tooler_container_name(cluster_name)}-{forward[0]}",
                command=_cmd,
                restart_policy={"Name": "unless-stopped"},
                remove=False,
                detach=True,
                ports={f"{forward[0]}/tcp": int(forward[0])},
                environment=["KUBECONFIG=/tmp/.kube/config"],
                volumes=[f"{kubeconfig_path}:/tmp/.kube/config"],
            )
        except docker.errors.APIError as e:
            if e.status_code == 409:
                try:
                    _cmd = ["/bin/sh", "-c", f"{' '.join(forward[1])}"]
                    # retry
                    config.DOCKER.containers.get(
                        f"{_get_tooler_container_name(cluster_name)}-{forward[0]}"
                    ).remove()
                    config.DOCKER.containers.run(  # noqa
                        image=config.TOOLER_IMAGE,
                        name=f"{_get_tooler_container_name(cluster_name)}-{forward[0]}",
                        command=_cmd,
                        restart_policy={"Name": "unless-stopped"},
                        remove=False,
                        detach=True,
                        ports={f"{forward[0]}/tcp": int(forward[0])},
                        environment=["KUBECONFIG=/tmp/.kube/config"],
                        volumes=[f"{kubeconfig_path}:/tmp/.kube/config"],
                    )
                except docker.errors.APIError as e:
                    raise RuntimeError(
                        "Finally failed to set up local proxy for the Kubernetes API"
                    )
            else:
                logger.error(e)
                raise RuntimeError(
                    "Could not create the local proxy for the Kubernetes API"
                )


def _list_containers_by_prefix(
    config: ClientConfiguration, prefix: str
) -> List[Optional[Container]]:
    containers = config.DOCKER.containers.list()
    result = []
    for container in containers:
        if container.name.startswith(prefix):
            result.append(container)
    return result


def kill_kubeapi_portforwarding(config: ClientConfiguration, cluster_name: str) -> None:
    try:
        config.K8S_CUSTOM_OBJECT_API.get_namespaced_custom_object(
            namespace=config.NAMESPACE,
            name=cluster_name,
            group="getdeck.dev",
            plural="beiboots",
            version="v1",
        )
    except k8s.client.exceptions.ApiException:
        pass

    try:
        containers = _list_containers_by_prefix(
            config, _get_tooler_container_name(cluster_name)
        )
        for container in containers:
            try:
                container.kill()
            except:  # noqa
                pass
            try:
                container.remove()
            except:  # noqa
                pass
    except docker.errors.APIError as e:
        logger.warning(str(e))
