from datetime import datetime
from typing import Optional

import kubernetes as k8s

CONFIGMAP_NAME = "beiboot-clients"

core_api = k8s.client.CoreV1Api()


def create_clients_heartbeat_configmap(logger, namespace: str) -> None:
    """
    It creates a ConfigMap in the namespace where the Beiboot is running

    :param logger: a logger object
    :param namespace: The namespace where the ConfigMap will be created
    :type namespace: str
    """
    configmap = k8s.client.V1ConfigMap(
        api_version="v1",
        kind="ConfigMap",
        data={},
        metadata=k8s.client.V1ObjectMeta(
            name=CONFIGMAP_NAME,
            namespace=namespace,
        ),
    )
    try:
        core_api.create_namespaced_config_map(namespace=namespace, body=configmap)
    except k8s.client.exceptions.ApiException as e:
        logger.error(e)
        logger.error(f"Cannot create ConfigMap for Beiboot clients: {e.reason}")


def get_latest_client_heartbeat(namespace: str) -> Optional[datetime]:
    """
    It reads the configmap, and returns the most recent heartbeat

    :param namespace: The namespace that the configmap is in
    :type namespace: str
    :return: The most recent heartbeat from the configmap.
    """
    try:
        configmap = core_api.read_namespaced_config_map(
            name=CONFIGMAP_NAME, namespace=namespace
        )
    except k8s.client.exceptions.ApiException as e:
        if e.status == 404:
            return None
        else:
            raise e
    clients = configmap.data
    if not clients:
        return None
    most_recent_connect: Optional[str] = None
    for _, heartbeat in clients.items():
        if not most_recent_connect:
            most_recent_connect = heartbeat
        else:
            if heartbeat > most_recent_connect:
                most_recent_connect = heartbeat
    if most_recent_connect:
        return datetime.fromisoformat(most_recent_connect)
    else:
        return None
