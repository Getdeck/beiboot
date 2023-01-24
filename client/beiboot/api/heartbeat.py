import logging
from datetime import datetime
from typing import Optional
from beiboot.configuration import ClientConfiguration, default_configuration
import kubernetes as k8s

from beiboot.api import stopwatch
from beiboot.types import Beiboot

logger = logging.getLogger(__name__)


@stopwatch
def write_heartbeat(
    client_id: str,
    bbt: Beiboot,
    timestamp: Optional[datetime] = None,
    config: ClientConfiguration = default_configuration,
) -> datetime:
    """
    Create a client contact entry to the heartbeat configmap for a Beiboot. Returns the timestamp written to the
    configmap.

    :param client_id: The client id to write the contact entry on behalf of
    :type client_id: str
    :param bbt: The Beiboot to write a heartbeat for
    :type bbt: Beiboot
    :param timestamp: Optional timestamp to write to the configmap
    :type timestamp: datetime
    """

    if timestamp is None:
        timestamp = datetime.utcnow()

    _timestamp = timestamp.isoformat()
    configmap = k8s.client.V1ConfigMap(  # type: ignore
        api_version="v1",
        kind="ConfigMap",
        data={client_id: _timestamp},
        metadata=k8s.client.V1ObjectMeta(  # type: ignore
            name=config.CLIENT_HEARTBEAT_CONFIGMAP_NAME,
            namespace=bbt.namespace,
        ),
    )
    try:
        config.K8S_CORE_API.patch_namespaced_config_map(
            name=config.CLIENT_HEARTBEAT_CONFIGMAP_NAME,
            namespace=bbt.namespace,
            body=configmap,
        )
        logger.debug(f"Successfully heartbeat for client {client_id} to {_timestamp}")
    except k8s.client.exceptions.ApiException as e:  # type: ignore
        if e.status == 404:
            raise RuntimeError(
                f"Cannot write heartbeat, the required configmap '{config.CLIENT_HEARTBEAT_CONFIGMAP_NAME}' does not exist"
            ) from None
        else:
            raise RuntimeError(f"Cannot write heartbeat: {e}") from None

    return timestamp
