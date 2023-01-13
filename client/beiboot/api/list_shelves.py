from typing import Dict
import kubernetes as k8s

from beiboot.api import stopwatch
from beiboot.configuration import ClientConfiguration, default_configuration
from beiboot.types import Shelf


@stopwatch
def read_all_shelves(
    labels: Dict[str, str] = {}, config: ClientConfiguration = default_configuration
) -> list[Shelf]:
    """
    Reads all Shelves.

    :param labels: A dictionary of labels to filter the Shelves by.
    :param config: The configuration to use.
    :return: A list of Shelves.
    """
    result = []
    if labels:
        _labels = ",".join([f"{label}={value}" for label, value in labels.items()])
    else:
        _labels = ""
    try:
        shelves = config.K8S_CUSTOM_OBJECT_API.list_namespaced_custom_object(
            group="beiboots.getdeck.dev",
            version="v1",
            namespace=config.NAMESPACE,
            plural="shelves",
            label_selector=_labels,
        )
    except k8s.client.ApiException as e:  # type: ignore
        if e.status == 404:
            raise RuntimeError(
                "This cluster does probably not support Getdeck Beiboot, or is not ready."
            ) from None
        else:
            raise RuntimeError(str(e)) from None
    else:
        for shelf in shelves["items"]:
            result.append(Shelf(shelf))
    return result
