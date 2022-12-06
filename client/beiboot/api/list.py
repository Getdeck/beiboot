import kubernetes as k8s

from beiboot.api import stopwatch
from beiboot.configuration import ClientConfiguration, default_configuration
from beiboot.types import Beiboot


@stopwatch
def read_all(config: ClientConfiguration = default_configuration) -> list[Beiboot]:
    result = []
    try:
        bbts = config.K8S_CUSTOM_OBJECT_API.list_namespaced_custom_object(
            group="getdeck.dev",
            version="v1",
            namespace=config.NAMESPACE,
            plural="beiboots",
        )
    except k8s.client.ApiException as e:
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
