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
        raise RuntimeError(str(e)) from None
    else:
        for bbt in bbts["items"]:
            result.append(Beiboot(bbt))
    return result
