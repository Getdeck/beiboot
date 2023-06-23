import json
import logging

import kubernetes as k8s

from beiboot.api.utils import stopwatch
from beiboot.configuration import default_configuration, ClientConfiguration
from beiboot.types import ShelfRequest, Shelf
from beiboot.utils import create_shelf_custom_ressource

logger = logging.getLogger(__name__)


@stopwatch
def create_shelf(
    req: ShelfRequest, config: ClientConfiguration = default_configuration
) -> Shelf:
    """
    It creates a Shelf

    :param req: ShelfRequest
    :type req: ShelfRequest
    :param config: ClientConfiguration = default_configuration
    :type config: ClientConfiguration
    :return: A Shelf object
    """
    logger.debug("creating shelf")
    obj = create_shelf_custom_ressource(req, config)
    try:
        logger.debug("Checking if Shelf object already exists")
        _ = config.K8S_CUSTOM_OBJECT_API.get_namespaced_custom_object(
            group="beiboots.getdeck.dev",
            version="v1",
            namespace=config.NAMESPACE,
            plural="shelves",
            name=req.name,
        )
        raise RuntimeError(
            f"The requested Shelf object '{req.name}' already exists. You can list existing shelves with 'shelf list'."
        )
    except k8s.client.exceptions.ApiException:  # type: ignore
        logger.debug("Shelf object does not exist and can be created")
        pass
    try:
        shelf = config.K8S_CUSTOM_OBJECT_API.create_namespaced_custom_object(
            namespace=config.NAMESPACE,
            body=obj,
            group="beiboots.getdeck.dev",
            plural="shelves",
            version="v1",
        )
        logger.debug(f"Successfully created Shelf object: {obj['metadata']['name']}")
    except k8s.client.exceptions.ApiException as e:  # type: ignore
        if e.status == 404:
            raise RuntimeError(
                "This cluster does probably not support Getdeck Beiboot, or is not ready."
            ) from None
        elif e.status == 500:
            raise RuntimeError(
                f"The requested Shelf {req.name} cannot be created: {json.loads(e.body).get('message')}"
            ) from None
        else:
            # TODO handle this case
            raise
    _shelf = Shelf(shelf)
    return _shelf
