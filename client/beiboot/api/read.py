import kubernetes as k8s

from beiboot.api import stopwatch
from beiboot.configuration import ClientConfiguration, default_configuration
from beiboot.types import Beiboot


@stopwatch
def read(name: str, config: ClientConfiguration = default_configuration) -> Beiboot:
    """
    Reads a Beiboot from the Kubernetes API.

    :param name: The name of the Beiboot to read.
    :param config: The configuration to use.
    :return: The Beiboot.
    :raises RuntimeError: If the Beiboot does not exist.
    """
    try:
        bbt = config.K8S_CUSTOM_OBJECT_API.get_namespaced_custom_object(
            group="getdeck.dev",
            version="v1",
            namespace=config.NAMESPACE,
            plural="beiboots",
            name=name,
        )
    except k8s.client.ApiException as e:  # type: ignore
        if e.status == 404:
            raise RuntimeError(f"The Beiboot {name} does not exist")
        raise RuntimeError(str(e)) from None
    return Beiboot(bbt)  # type: ignore
