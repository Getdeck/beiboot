from datetime import datetime
from typing import Optional

import kubernetes as k8s

CONFIGMAP_NAME = "beiboot-clients"

core_api = k8s.client.CoreV1Api()


def create_clients_heartbeat_configmap(logger, namespace: str) -> None:
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
    most_recent_connect = None
    for client, heartbeat in clients.items():
        if not most_recent_connect:
            most_recent_connect = heartbeat
        else:
            if heartbeat > most_recent_connect:
                most_recent_connect = heartbeat
    return datetime.fromisoformat(most_recent_connect)
