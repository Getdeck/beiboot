import kopf
import kubernetes as k8s

from beiboot.configuration import configuration, ClusterConfiguration
from beiboot.utils import get_namespace_name

@kopf.on.validate("beiboot.getdeck.dev", id="set-namespace")  # type: ignore
def set_beiboot_namespace(body, patch, logger, operation, **_):

    if operation == "CREATE":
        cluster_config = configuration.refresh_k8s_config()
        patch.spec["beibootNamespace"] = get_namespace_name(self.name, cluster_config)
    else:
        return
