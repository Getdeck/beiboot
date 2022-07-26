import base64
import logging
import os
import pathlib
from typing import List

import docker.errors
import kubernetes as k8s
from beiboot.configuration import ClientConfiguration

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
    command = []
    for idx, port in enumerate(forwarded_ports):
        if idx != 0:
            command.extend(["&"])
        command.extend(
            [
                "(while true; do " "kubectl",
                "port-forward",
                "-n",
                bbt["beibootNamespace"],
                f"svc/port-{port.split(':')[1]}",
                port,
                "; done)",
            ]
        )
    if forwarded_ports:
        command.extend(["&"])
    command.extend(
        [
            "kubectl",
            "port-forward",
            "-n",
            bbt["beibootNamespace"],
            "svc/kubeapi",
            f"{config.BEIBOOT_API_PORT}:{config.BEIBOOT_API_PORT}",
        ]
    )
    if config.KUBECONFIG_FILE:
        kubeconfig_path = config.KUBECONFIG_FILE
    else:
        from kubernetes.config import kube_config

        kubeconfig_path = os.path.expanduser(kube_config.KUBE_CONFIG_DEFAULT_LOCATION)
    try:
        _cmd = ["/bin/sh", "-c", f"{' '.join(command)}"]
        logger.debug(_cmd)
        container = config.DOCKER.containers.run(  # noqa
            image=config.TOOLER_IMAGE,
            name=_get_tooler_container_name(cluster_name),
            command=_cmd,
            restart_policy={"Name": "unless-stopped"},
            remove=False,
            detach=True,
            network_mode="host",
            environment=["KUBECONFIG=/tmp/.kube/config"],
            volumes=[f"{kubeconfig_path}:/tmp/.kube/config"],
        )
    except docker.errors.APIError as e:
        logger.error(e)
        raise RuntimeError("Could not create the local proxy for the Kubernetes API")


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
        container = config.DOCKER.containers.get(
            _get_tooler_container_name(cluster_name),
        )
        try:
            container.kill()
        except:  # noqa
            pass
        container.remove()
    except docker.errors.APIError as e:
        logger.warning(str(e))
