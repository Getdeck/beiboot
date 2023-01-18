import base64
import logging
import socket
from pathlib import Path
from typing import List, Optional, Container

from beiboot.configuration import ClientConfiguration, __VERSION__

from beiboot.types import BeibootRequest, ShelfRequest

logger = logging.getLogger(__name__)


def create_beiboot_custom_ressource(
    req: BeibootRequest, config: ClientConfiguration
) -> dict:
    _labels = req.labels
    _labels.update({"beiboot.getdeck.dev/client-version": __VERSION__})
    cr = {
        "apiVersion": "getdeck.dev/v1",
        "kind": "beiboot",
        "provider": "k3s",
        "parameters": req.parameters.as_dict(),
        "fromShelf": req.from_shelf,
        "metadata": {
            "name": req.name,
            "namespace": config.NAMESPACE,
            "labels": _labels,
        },
    }
    return cr


def create_shelf_custom_ressource(
    req: ShelfRequest, config: ClientConfiguration
) -> dict:
    _labels = req.labels
    _labels.update({"beiboot.getdeck.dev/client-version": __VERSION__})
    cr = {
        "apiVersion": "beiboots.getdeck.dev/v1",
        "kind": "shelf",
        "clusterName": req.cluster_name,
        "volumeSnapshotClass": req.volume_snapshot_class,
        "volumeSnapshotContents": req.volume_snapshot_contents,
        "metadata": {
            "name": req.name,
            "namespace": config.NAMESPACE,
            "labels": _labels,
        },
    }
    return cr


def decode_kubeconfig(kubeconfig_obj: dict):
    """
    It takes a dictionary with a key called `source` and returns the value of that key decoded from base64

    :param kubeconfig_obj: The kubeconfig object that we created in the previous step
    :type kubeconfig_obj: dict
    :return: A string of the kubeconfig
    """
    b64_kubeconfig = kubeconfig_obj["source"]
    kubeconfig = base64.b64decode(b64_kubeconfig.encode("utf-8")).decode("utf-8")
    return kubeconfig


def get_beiboot_config_location(config: ClientConfiguration, cluster_name: str) -> str:
    """
    It creates a directory for the cluster's configuration file if it doesn't already exist, and returns the path to
    that directory

    :param config: ClientConfiguration
    :type config: ClientConfiguration
    :param cluster_name: The name of the cluster you want to create
    :type cluster_name: str
    :return: The path to the directory where the kubeconfig file will be stored.
    """
    config_dir = config.KUBECONFIG_LOCATION.joinpath(cluster_name)
    config_dir.mkdir(parents=True, exist_ok=True)
    return str(config_dir)


def get_kubeconfig_location(config: ClientConfiguration, cluster_name: str) -> str:
    """
    It returns the location of the kubeconfig file for a given cluster name

    :param config: This is the configuration object that we created earlier
    :type config: ClientConfiguration
    :param cluster_name: The name of the Beiboot cluster you want to create
    :type cluster_name: str
    :return: The path to the kubeconfig file for the cluster.
    """
    return str(
        Path(get_beiboot_config_location(config, cluster_name)).joinpath(
            f"{cluster_name}.yaml"
        )
    )


def decode_b64_dict(b64_dict: dict[str, str]) -> dict[str, str]:
    """
    It takes a dictionary of base64 encoded strings and returns a dictionary of decoded strings

    :param b64_dict: a dictionary of key-value pairs where the value is a base64-encoded string
    :type b64_dict: dict[str, str]
    :return: A dictionary with the keys and values decoded from base64.
    """
    return {
        k: base64.b64decode(v.encode("utf-8")).decode("utf-8").strip()
        for k, v in b64_dict.items()
    }


def _check_port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
        except OSError:
            raise RuntimeError(
                f"Can not establish requested connection: localhost:{port} is busy."
            ) from None
        else:
            s.close()
    return True


def _list_containers_by_prefix(
    config: ClientConfiguration, prefix: str
) -> List[Optional[Container]]:
    """
    It returns a list of all containers whose name starts with a given prefix

    :param config: ClientConfiguration
    :type config: ClientConfiguration
    :param prefix: The prefix of the container name
    :type prefix: str
    :return: A list of containers that start with the prefix.
    """

    containers = config.DOCKER.containers.list()
    result = []
    for container in containers:
        if container.name.startswith(prefix):  # type: ignore
            result.append(container)
    return result
