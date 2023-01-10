import logging

import kubernetes as k8s

from beiboot.api import stopwatch
from beiboot.configuration import ClientConfiguration, default_configuration
from beiboot.types import Beiboot


logger = logging.getLogger(__name__)


@stopwatch
def delete(bbt: Beiboot, config: ClientConfiguration = default_configuration) -> None:
    """
    Mark a Beiboot for deletion

    :param bbt: The Beiboot to be marked for deletion
    :type bbt: Beiboot
    """
    _delete_bbt(bbt.name, config)


@stopwatch
def delete_by_name(
    name: str, config: ClientConfiguration = default_configuration
) -> None:
    """
    Mark a Beiboot for deletion

    :param name: The Beiboot name to be marked for deletion
    :type name: str
    """
    _delete_bbt(name, config)


def _delete_bbt(cluster_name: str, config: ClientConfiguration):
    logger.debug(f"Now removing Beiboot {cluster_name}")
    try:
        config.K8S_CUSTOM_OBJECT_API.delete_namespaced_custom_object(
            namespace=config.NAMESPACE,
            name=cluster_name,
            group="getdeck.dev",
            plural="beiboots",
            version="v1",
        )
        logger.debug(f"Successfully deleted Beiboot {cluster_name}")
    except k8s.client.exceptions.ApiException as e:  # type: ignore
        if e.status == 404:
            #  Getdeck Beiboot probably not available
            raise RuntimeWarning(f"Beiboot {cluster_name} does not exist")
        else:
            raise RuntimeError(
                f"Error deleting Beiboot object: {e.reason} ({e.status})"
            )
