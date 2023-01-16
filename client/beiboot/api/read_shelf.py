import kubernetes as k8s

from beiboot.api import stopwatch
from beiboot.configuration import ClientConfiguration, default_configuration
from beiboot.types import Shelf


@stopwatch
def read_shelf(name: str, config: ClientConfiguration = default_configuration) -> Shelf:
    """
    Reads a Shelf from the Kubernetes API.

    :param name: The name of the Shelf to read.
    :param config: The configuration to use.
    :return: The Shelf.
    :raises RuntimeError: If the Shelf does not exist.
    """
    try:
        shelf = config.K8S_CUSTOM_OBJECT_API.get_namespaced_custom_object(
            group="beiboots.getdeck.dev",
            version="v1",
            namespace=config.NAMESPACE,
            plural="shelves",
            name=name,
        )
    except k8s.client.ApiException as e:  # type: ignore
        if e.status == 404:
            raise RuntimeError(f"The Shelf {name} does not exist")
        raise RuntimeError(str(e)) from None
    return Shelf(shelf)  # type: ignore
