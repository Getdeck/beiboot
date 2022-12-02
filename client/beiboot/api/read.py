import kubernetes as k8s

from beiboot.api import stopwatch
from beiboot.configuration import ClientConfiguration, default_configuration
from beiboot.types import Beiboot


@stopwatch
def read(name: str, config: ClientConfiguration = default_configuration) -> Beiboot:
    try:
        bbt = config.K8S_CUSTOM_OBJECT_API.get_namespaced_custom_object(
            group="getdeck.dev",
            version="v1",
            namespace=config.NAMESPACE,
            plural="beiboots",
            name=name,
        )
    except k8s.client.ApiException as e:
        if e.status == 404:
            raise RuntimeError(f"The Beiboot {name} does not exist")
        raise RuntimeError(str(e)) from None
    return Beiboot(bbt)
