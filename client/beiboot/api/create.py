import json

import kubernetes as k8s

from beiboot.api.utils import stopwatch
from beiboot.configuration import default_configuration, ClientConfiguration
from beiboot.types import BeibootRequest, Beiboot
from beiboot.utils import create_beiboot_custom_ressource


@stopwatch
def create(
    req: BeibootRequest, config: ClientConfiguration = default_configuration
) -> Beiboot:
    obj = create_beiboot_custom_ressource(req, config)
    try:
        _ = config.K8S_CUSTOM_OBJECT_API.get_namespaced_custom_object(
            group="getdeck.dev",
            version="v1",
            namespace=config.NAMESPACE,
            plural="beiboots",
            name=req.name,
        )
        raise RuntimeError(f"The requested Beiboot cluster {req.name} already exists.")
    except k8s.client.exceptions.ApiException:
        # that is ok
        pass

    try:
        bbt = config.K8S_CUSTOM_OBJECT_API.create_namespaced_custom_object(
            namespace=config.NAMESPACE,
            body=obj,
            group="getdeck.dev",
            plural="beiboots",
            version="v1",
        )
    except k8s.client.exceptions.ApiException as e:
        if e.status == 404:
            raise RuntimeError(
                "This cluster does probably not support Getdeck Beiboot, or is not ready."
            ) from None
        elif e.status == 409:
            # this cluster already exists
            raise RuntimeError(
                f"The requested Beiboot cluster {req.name} already exists."
            ) from None
        elif e.status == 500:
            raise RuntimeError(
                f"The requested Beiboot cluster {req.name} cannot be created: {json.loads(e.body).get('message')}"
            ) from None
        else:
            # TODO handle this case
            raise

    return Beiboot(bbt)
