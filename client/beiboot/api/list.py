from typing import Dict
import kubernetes as k8s

from beiboot.api import stopwatch
from beiboot.configuration import ClientConfiguration, default_configuration
from beiboot.types import Beiboot


@stopwatch
def read_all(
    labels: Dict[str, str] = {}, config: ClientConfiguration = default_configuration
) -> list[Beiboot]:
    """
    Reads all Beiboots from the cluster.

    :param labels: A dictionary of labels to filter the Beiboots by.
    :param config: The configuration to use.
    :return: A list of Beiboots.
    """
    result = []
    if labels:
        _labels = ",".join([f"{label}={value}" for label, value in labels.items()])
    else:
        _labels = ""
    try:
        bbts = config.K8S_CUSTOM_OBJECT_API.list_namespaced_custom_object(
            group="getdeck.dev",
            version="v1",
            namespace=config.NAMESPACE,
            plural="beiboots",
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
        for bbt in bbts["items"]:
            result.append(Beiboot(bbt))
    return result
