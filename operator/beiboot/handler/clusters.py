import kubernetes as k8s
import kopf

from beiboot.clusterstate import BeibootCluster
from beiboot.configuration import configuration

core_api = k8s.client.CoreV1Api()
objects_api = k8s.client.CustomObjectsApi()


def in_any_beiboot_namespace(event, namespace, **_):
    beiboots = objects_api.list_namespaced_custom_object(
        group="getdeck.dev",
        version="v1",
        namespace=configuration.NAMESPACE,
        plural="beiboots",
    )
    namespaces = set(bbt.get("beibootNamespace") for bbt in beiboots["items"])
    return namespace in namespaces and event["object"]["involvedObject"]["kind"] in ["StatefulSet", "Deployment"]


def get_beiboot_for_namespace(namespace: str):
    class AttrDict(dict):
        def __init__(self, *args, **kwargs):
            super(AttrDict, self).__init__(*args, **kwargs)
            self.__dict__ = self

    beiboots = objects_api.list_namespaced_custom_object(
        group="getdeck.dev",
        version="v1",
        namespace=configuration.NAMESPACE,
        plural="beiboots",
    )
    for bbt in beiboots["items"]:
        if bbt["beibootNamespace"] == namespace:
            # need to wrap this for correct later use
            return AttrDict(bbt)
    else:
        return None


@kopf.on.event("event", when=in_any_beiboot_namespace)
async def handle_cluster_workload_events(event, namespace, logger, **kwargs):
    beiboot = get_beiboot_for_namespace(namespace)
    if beiboot is None:
        logger.warn(f"The Beiboot object for namespace '{namespace}' does not exist")
        return
    parameters = configuration.refresh_k8s_config()
    cluster = BeibootCluster(configuration, parameters, model=beiboot, logger=logger)
    # drop events that have been prior to last state change of cluster

    if cluster.current_state == BeibootCluster.running or cluster.current_state == BeibootCluster.ready:
        try:
            await cluster.reconcile()
        except (kopf.PermanentError, kopf.TemporaryError) as e:
            print(e)
            await cluster.on_impair(str(e))
            print("blubb")
            raise e
    elif cluster.current_state == BeibootCluster.creating:
        # this cluster is just booting up
        if reason := event["object"].get("reason"):
            kopf.info(beiboot, reason=reason, message=event["object"].get("message", ""))
    elif cluster.current_state == BeibootCluster.error:
        await cluster.reconcile()
