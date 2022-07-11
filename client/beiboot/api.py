import logging
from pathlib import Path
from time import sleep

import kubernetes as k8s

from beiboot.configuration import ClientConfiguration, default_configuration
from beiboot.utils import (
    create_beiboot_custom_ressource,
    decode_kubeconfig,
    save_kubeconfig_to_file,
    delete_kubeconfig_file,
)

from beiboot.utils import (
    get_kubeconfig_location,
    start_kubeapi_portforwarding,
    kill_kubeapi_portforwarding,
)

logger = logging.getLogger("getdeck.beiboot")


def create_cluster(
    cluster_name: str,
    connect: bool = True,
    configuration: ClientConfiguration = default_configuration,
) -> None:
    #
    # 1. create the CR object for Beiboot; apply it
    #
    logger.info(f"Now creating Beiboot {cluster_name}")
    obj = create_beiboot_custom_ressource(configuration, cluster_name)
    try:
        bbt = configuration.K8S_CUSTOM_OBJECT_API.create_namespaced_custom_object(
            namespace=configuration.NAMESPACE,
            body=obj,
            group="getdeck.dev",
            plural="beiboots",
            version="v1",
        )
    except k8s.client.exceptions.ApiException as e:
        if e.status == 404:
            #  Getdeck Beiboot probably not available
            # TODO handle this case
            raise
        elif e.status == 409:
            # this cluster already exists
            raise RuntimeError(
                f"The requested cluster name {cluster_name} already exists."
            )
        else:
            # TODO handle that case
            raise

    #
    # 2. Wait for the kubeconfig
    #
    logger.info("Waiting for the cluster to become ready")

    i = 0
    while configuration.CLUSTER_CREATION_TIMEOUT > i:
        try:
            bbt = configuration.K8S_CUSTOM_OBJECT_API.get_namespaced_custom_object(
                group="getdeck.dev",
                version="v1",
                namespace=configuration.NAMESPACE,
                plural="beiboots",
                name=bbt["metadata"]["name"],
            )
        except k8s.client.exceptions.ApiException as e:
            raise e
        if bbt.get("kubeconfig"):
            # if the kubeconfig was added, this cluster is ready
            break
        else:
            i = i + 1
            sleep(1)
    #
    # 3. store the kubeconfig to a well-known place
    #
    kubeconfig_object = bbt.get("kubeconfig")
    kubeconfig = decode_kubeconfig(kubeconfig_object)
    kubeconfig_file = save_kubeconfig_to_file(configuration, cluster_name, kubeconfig)
    logger.info(f"KUBECONFIG file for {cluster_name} written to: {kubeconfig_file}.")
    if connect:
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
            # TODO handle this case
            raise
        else:
            # TODO  handle that case
            raise
    delete_kubeconfig_file(configuration, cluster_name)
    kill_kubeapi_portforwarding(configuration, cluster_name)


def get_connection() -> str:
    pass


def establish_connection(
    cluster_name: str, configuration: ClientConfiguration = default_configuration
) -> None:
    kubeconfig_location = get_kubeconfig_location(configuration, cluster_name)
    kubeconfig = Path(kubeconfig_location)
    if not kubeconfig.is_file():
        raise RuntimeError(
            f"KUBECONFIG for cluster {cluster_name} not found. Cannot establish a connection."
        )
    start_kubeapi_portforwarding(configuration, cluster_name)
    logger.info(
        f"You can now set 'export KUBECONFIG={kubeconfig_location}' and work with the cluster."
    )
