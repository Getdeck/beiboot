import json
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
    probe_portforwarding,
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
    probe_connection: bool = True,
    configuration: ClientConfiguration = default_configuration,
) -> None:

    if ports is None:
        ports = []
    obj = create_beiboot_custom_ressource(configuration, cluster_name, ports)
    try:
        _ = configuration.K8S_CUSTOM_OBJECT_API.get_namespaced_custom_object(
            group="getdeck.dev",
            version="v1",
            namespace=configuration.NAMESPACE,
            plural="beiboots",
            name=cluster_name,
        )
        raise RuntimeError(
            f"The requested Beiboot cluster {cluster_name} already exists."
        )
    except k8s.client.exceptions.ApiException:
        # that is ok
        pass

    #
    # 1. create the CR object for Beiboot; apply it
    #
    logger.info(f"Now creating Beiboot {cluster_name}")
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
            raise RuntimeError(
                "This cluster does probably not support Getdeck Beiboot, or is not ready."
            ) from None
        elif e.status == 409:
            # this cluster already exists
            raise RuntimeError(
                f"The requested Beiboot cluster {cluster_name} already exists."
            ) from None
        elif e.status == 500:
            raise RuntimeError(
                f"The requested Beiboot cluster {cluster_name} cannot be created: {json.loads(e.body).get('message')}"
            ) from None
        else:
            # TODO handle that case
            raise

    w = k8s.watch.Watch()

    # wait for cluster events side is ready
    for _object in w.stream(
        configuration.K8S_CORE_API.list_namespaced_event,
        namespace=configuration.NAMESPACE,
    ):
        event = _object.get("object")
        if (
            event.involved_object.kind == "beiboot"
            and event.involved_object.uid == bbt["metadata"]["uid"]
        ):
            logger.debug(f"{event.reason} -> {event.message}")
            if event.reason == "Ready":
                logger.info(f"The Beiboot cluster {cluster_name} is ready")
                break
            elif event.reason == "Failedscheduling":
                logger.warning(
                    f"The Beiboot cluster may not be able to be scheduled: {event.message}"
                )
            elif event.reason == "Triggeredscaleup":
                logger.warning(
                    f"The host cluster triggered a node scale-up: {event.message}"
                )
            elif event.reason == "Error":
                logger.error(event.message)
                break

    # if connect:
    #     logger.info(
    #         "Now connecting to the cluster; this may take a while to complete. "
    #     )
    #     establish_connection(cluster_name, probe_connection, configuration)


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
                raise RuntimeError(
                    f"This Beiboot cluster {cluster_name} does not exist"
                ) from None
            else:
                raise RuntimeError(
                    f"Error fetching the Beiboot object: {e.reason}"
                ) from None
        if bbt.get("state") == "READY":
            break
        else:
            logger.debug(
                f"Waiting for the cluster to become ready {i}/{configuration.CLUSTER_CREATION_TIMEOUT}"
            )
            i = i + 1
            sleep(1)
    else:
        raise TimeoutError(
            f"The cluster could not be created in time (timeout: {configuration.CLUSTER_CREATION_TIMEOUT} s)"
        )
    #
    # 2. store the kubeconfig to a well-known place
    #
    kubeconfig_object = bbt.get("kubeconfig")  # noqa
    kubeconfig = decode_kubeconfig(kubeconfig_object)
    kubeconfig_file = save_kubeconfig_to_file(configuration, cluster_name, kubeconfig)
    logger.info(f"KUBECONFIG file for {cluster_name} written to: {kubeconfig_file}.")
    return kubeconfig_file


def establish_connection(
    cluster_name: str,
    probe_connection: bool = True,
    configuration: ClientConfiguration = default_configuration,
) -> None:

    kubeconfig_location = get_connection(cluster_name, configuration)
    kubeconfig = Path(kubeconfig_location)
    if not kubeconfig.is_file():
        raise RuntimeError(
            f"KUBECONFIG for cluster {cluster_name} not found. Cannot establish a connection."
        )
    start_kubeapi_portforwarding(configuration, cluster_name)
    if probe_connection:
        probe_portforwarding(configuration, cluster_name)

    logger.info(
        f"You can now set 'export KUBECONFIG={kubeconfig_location}' and work with the cluster."
    )


def terminate_connection(
    cluster_name: str, configuration: ClientConfiguration = default_configuration
) -> None:
    kill_kubeapi_portforwarding(configuration, cluster_name)
