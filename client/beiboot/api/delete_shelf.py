import logging

import kubernetes as k8s

from beiboot.api import stopwatch
from beiboot.configuration import ClientConfiguration, default_configuration
from beiboot.types import Shelf

logger = logging.getLogger(__name__)


@stopwatch
def delete_shelf(
    shelf: Shelf, config: ClientConfiguration = default_configuration
) -> None:
    """
    Mark a Shelf for deletion

    :param shelf: The Shelf to be marked for deletion
    :type shelf: Shelf
    """
    _delete_shelf(shelf.name, config)


@stopwatch
def delete_shelf_by_name(
    name: str, config: ClientConfiguration = default_configuration
) -> None:
    """
    Mark a Shelf for deletion

    :param name: The Shelf name to be marked for deletion
    :type name: str
    """
    _delete_shelf(name, config)


def _delete_shelf(shelf_name: str, config: ClientConfiguration):
    logger.debug(f"Now removing Shelf {shelf_name}")
    try:
        config.K8S_CUSTOM_OBJECT_API.delete_namespaced_custom_object(
            namespace=config.NAMESPACE,
            name=shelf_name,
            group="beiboots.getdeck.dev",
            plural="shelves",
            version="v1",
        )
        logger.debug(f"Successfully deleted Shelf {shelf_name}")
    except k8s.client.exceptions.ApiException as e:  # type: ignore
        if e.status == 404:
            #  Getdeck Beiboot probably not available
            raise RuntimeWarning(f"Shelf {shelf_name} does not exist")
        else:
            raise RuntimeError(f"Error deleting Shelf object: {e.reason} ({e.status})")
