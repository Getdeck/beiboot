import json
import logging

import kubernetes as k8s

from beiboot.api.utils import stopwatch
from beiboot.configuration import default_configuration, ClientConfiguration
from beiboot.types import BeibootRequest, Beiboot
from beiboot.utils import create_beiboot_custom_ressource

logger = logging.getLogger(__name__)


@stopwatch
def create(
    req: BeibootRequest, config: ClientConfiguration = default_configuration
) -> Beiboot:
    """
    It creates a Beiboot cluster

    :param req: BeibootRequest
    :type req: BeibootRequest
    :param config: ClientConfiguration = default_configuration
    :type config: ClientConfiguration
    :return: A Beiboot object
    """
    obj = create_beiboot_custom_ressource(req, config)
    try:
        logger.debug("Checking if Beiboot object already exists")
        _ = config.K8S_CUSTOM_OBJECT_API.get_namespaced_custom_object(
            group="getdeck.dev",
            version="v1",
            namespace=config.NAMESPACE,
            plural="beiboots",
            name=req.name,
        )
        raise RuntimeError(
            f"The requested Beiboot cluster '{req.name}' already exists."
        )
    except k8s.client.exceptions.ApiException:  # type: ignore
        logger.debug("Beiboot object does not exist and can be created")
        pass
    try:
        bbt = config.K8S_CUSTOM_OBJECT_API.create_namespaced_custom_object(
            namespace=config.NAMESPACE,
            body=obj,
            group="getdeck.dev",
            plural="beiboots",
            version="v1",
        )
        logger.debug(f"Successfully created Beiboot object: {obj['metadata']['name']}")
    except k8s.client.exceptions.ApiException as e:  # type: ignore
        if e.status == 404:
            raise RuntimeError(
                "This cluster does probably not support Getdeck Beiboot, or is not ready."
            ) from None
        elif e.status == 500:
            raise RuntimeError(
                f"The requested Beiboot cluster {req.name} cannot be created: {json.loads(e.body).get('message')}"
            ) from None
        else:
            # TODO handle this case
            raise
    _beiboot = Beiboot(bbt)
    return _beiboot
