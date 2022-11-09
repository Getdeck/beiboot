from datetime import datetime

import kubernetes as k8s
import kopf

from beiboot.clusterstate import BeibootCluster
from beiboot.configuration import configuration

core_api = k8s.client.CoreV1Api()
objects_api = k8s.client.CustomObjectsApi()


def _in_any_beiboot_namespace(event, namespace, kind: list, **_):
    beiboots = objects_api.list_namespaced_custom_object(
        group="getdeck.dev",
        version="v1",
        namespace=configuration.NAMESPACE,
        plural="beiboots",
    )
    namespaces = set(bbt.get("beibootNamespace") for bbt in beiboots["items"])
    return namespace in namespaces and event["object"]["involvedObject"]["kind"] in kind


def workloads_in_beiboot_namespace(event, namespace, **_):
    return _in_any_beiboot_namespace(
        event, namespace, kind=["StatefulSet", "Deployment", "Pod"]
    )


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


@kopf.on.event(
    "event",
    when=kopf.all_(
        [lambda event, **_: event["type"] is not None, workloads_in_beiboot_namespace]
    ),
)
async def handle_cluster_workload_events(event, namespace, logger, **kwargs):
    beiboot = get_beiboot_for_namespace(namespace)
    if beiboot is None:
        logger.warn(f"The Beiboot object for namespace '{namespace}' does not exist")
        return
    parameters = configuration.refresh_k8s_config()
    cluster = BeibootCluster(configuration, parameters, model=beiboot, logger=logger)
    # drop events that have been prior to last state change of cluster
    if creationTimestamp := event["object"]["metadata"].get("creationTimestamp"):
        event_timestamp = datetime.fromisoformat(creationTimestamp.strip("Z"))
        if ready_timestamp := cluster.completed_transition(BeibootCluster.ready.value):
            if event_timestamp < datetime.fromisoformat(ready_timestamp.strip("Z")):
                logger.debug(
                    "Dropping event because event timestamp older than ready timestamp of cluster"
                )
                return
        if running_timestamp := cluster.completed_transition(
            BeibootCluster.running.value
        ):
            if event_timestamp < datetime.fromisoformat(running_timestamp.strip("Z")):
                logger.debug(
                    "Dropping event because event timestamp older than running timestamp of cluster"
                )
                return

    if (
        cluster.current_state == BeibootCluster.running
        or cluster.current_state == BeibootCluster.ready
    ):
        if reason := event["object"].get("reason"):
            cluster.post_event(reason, message=event["object"].get("message", ""))
        try:
            await cluster.reconcile()
        except (kopf.PermanentError, kopf.TemporaryError) as e:
            logger.error(e)
            await cluster.impair(str(e))
            raise e
    elif cluster.current_state == BeibootCluster.creating:
        # this cluster is just booting up
        if reason := event["object"].get("reason"):
            cluster.post_event(reason, message=event["object"].get("message", ""))
    elif cluster.current_state == BeibootCluster.error and cluster.completed_transition(
        BeibootCluster.running.value
    ):
        await cluster.recover()
