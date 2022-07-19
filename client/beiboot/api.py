import logging
from pathlib import Path
from time import sleep
from typing import List

import kubernetes as k8s

from beiboot.configuration import ClientConfiguration, default_configuration
from beiboot.utils import (
    create_beiboot_custom_ressource,
    decode_kubeconfig,
    save_kubeconfig_to_file,
    delete_kubeconfig_file,
)

from beiboot.utils import (
    start_kubeapi_portforwarding,
    kill_kubeapi_portforwarding,
)

logger = logging.getLogger("getdeck.beiboot")


def create_cluster(
    cluster_name: str,
    ports: List[str] = None,
    connect: bool = True,
    configuration: ClientConfiguration = default_configuration,
) -> None:
    #
    # 1. create the CR object for Beiboot; apply it
    #
    logger.info(f"Now creating Beiboot {cluster_name}")
    if ports is None:
        ports = []
    obj = create_beiboot_custom_ressource(configuration, cluster_name, ports)
    try:
        configuration.K8S_CUSTOM_OBJECT_API.create_namespaced_custom_object(
            namespace=configuration.NAMESPACE,
            body=obj,
            group="getdeck.dev",
            plural="beiboots",
            version="v1",
        )
    except k8s.client.exceptions.ApiException as e:
        if e.status == 404:
            raise RuntimeError(
                "This cluster does probably not support Getdeck Beiboot, or is not ready."
            )
        elif e.status == 409:
            # this cluster already exists
            raise RuntimeError(
                f"The requested cluster name {cluster_name} already exists."
            )
        else:
            # TODO handle that case
            raise

    if connect:
        logger.info(
            "Now connecting to the cluster; this may take a while to complete. "
        )
        establish_connection(cluster_name, configuration)


def remove_cluster(
    cluster_name: str, configuration: ClientConfiguration = default_configuration
) -> None:
    logger.info(f"Now removing Beiboot {cluster_name}")
    try:
        configuration.K8S_CUSTOM_OBJECT_API.delete_namespaced_custom_object(
            namespace=configuration.NAMESPACE,
            name=cluster_name,
            group="getdeck.dev",
            plural="beiboots",
            version="v1",
        )
    except k8s.client.exceptions.ApiException as e:
        logger.error(f"Error deleting Beiboot object: {e.reason} ({e.status})")
        if e.status == 404:
            #  Getdeck Beiboot probably not available
            pass
        else:
            # TODO  handle that case
            raise
    delete_kubeconfig_file(configuration, cluster_name)
    kill_kubeapi_portforwarding(configuration, cluster_name)


def get_connection(
    cluster_name: str, configuration: ClientConfiguration = default_configuration
) -> str:
    #
    # 1. Wait for the kubeconfig
    #
    i = 0
    while configuration.CLUSTER_CREATION_TIMEOUT > i:
        try:
            bbt = configuration.K8S_CUSTOM_OBJECT_API.get_namespaced_custom_object(
                group="getdeck.dev",
                version="v1",
                namespace=configuration.NAMESPACE,
                plural="beiboots",
                name=cluster_name,
            )
        except k8s.client.exceptions.ApiException as e:
            if e.status == 404:
                raise RuntimeError("This cluster name does not exist")
            else:
                raise RuntimeError(f"Error fetching the Beiboot object: {e.reason}")
        if bbt.get("kubeconfig"):
            # if the kubeconfig was added, this cluster is ready
            break
        else:
            logger.debug(
                f"Waiting for the cluster to become ready {i}/{configuration.CLUSTER_CREATION_TIMEOUT}"
            )
            i = i + 1
            sleep(1)
    #
    # 2. store the kubeconfig to a well-known place
    #
    kubeconfig_object = bbt.get("kubeconfig")  # noqa
    kubeconfig = decode_kubeconfig(kubeconfig_object)
    kubeconfig_file = save_kubeconfig_to_file(configuration, cluster_name, kubeconfig)
    logger.info(f"KUBECONFIG file for {cluster_name} written to: {kubeconfig_file}.")
    return kubeconfig_file


def establish_connection(
    cluster_name: str, configuration: ClientConfiguration = default_configuration
) -> None:

    kubeconfig_location = get_connection(cluster_name, configuration)
    kubeconfig = Path(kubeconfig_location)
    if not kubeconfig.is_file():
        raise RuntimeError(
            f"KUBECONFIG for cluster {cluster_name} not found. Cannot establish a connection."
        )
    start_kubeapi_portforwarding(configuration, cluster_name)
    logger.info(
        f"You can now set 'export KUBECONFIG={kubeconfig_location}' and work with the cluster."
    )


def terminate_connection(
    cluster_name: str, configuration: ClientConfiguration = default_configuration
) -> None:
    kill_kubeapi_portforwarding(configuration, cluster_name)
