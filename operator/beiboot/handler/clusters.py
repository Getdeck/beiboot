from datetime import datetime

import kubernetes as k8s
import kopf

from beiboot.clusterstate import BeibootCluster
from beiboot.configuration import configuration
from beiboot.utils import get_beiboot_for_namespace

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


def _workloads_in_beiboot_namespace(event, namespace, **_) -> bool:
    return _in_any_beiboot_namespace(
        event, namespace, kind=["StatefulSet", "Deployment", "Pod"]
    )


def _event_type_not_none(event, **_) -> bool:
    return "type" in event and event["type"] is not None


def _event_reason_not_in(event, **_) -> bool:
    if "object" in event:
        if reason := event["object"].get("reason"):
            # filter out these event reasons
            if reason in [
                "Pulled",
                "Created",
                "SuccessfulAttachVolume",
                "SuccessfulCreate",
            ]:
                return False
            else:
                return True
        else:
            return False
    else:
        return False


@kopf.on.event(
    "event",
    when=kopf.all_(  # type: ignore
        [_event_type_not_none, _workloads_in_beiboot_namespace, _event_reason_not_in]
    ),
)
async def handle_cluster_workload_events(event, namespace, logger, **kwargs):
    """
    It handles workload events for a cluster (such as StatefulSet, Deployment, Pod)

    :param event: The event that triggered the handler
    :param namespace: The namespace of the Beiboot object
    :param logger: The logger object that you can use to log messages
    :return: The return value of the handler function is ignored.
    """
    beiboot = get_beiboot_for_namespace(namespace, objects_api, configuration)
    if beiboot is None:
        logger.warn(f"The Beiboot object for namespace '{namespace}' does not exist")
        return
    parameters = configuration.refresh_k8s_config(beiboot.get("parameters"))
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

    if cluster.is_running or cluster.is_ready:
        if reason := event["object"].get("reason"):
            cluster.post_event(reason, message=event["object"].get("message", ""))
        try:
            await cluster.reconcile()
        except (kopf.PermanentError, kopf.TemporaryError) as e:
            logger.error(e)
            await cluster.impair(str(e))
            raise e
    elif cluster.is_creating or cluster.is_pending:
        # this cluster is just booting up
        if reason := event["object"].get("reason"):
            cluster.post_event(reason, message=event["object"].get("message", ""))
    elif cluster.is_error and cluster.completed_transition(
        BeibootCluster.running.value
    ):
        await cluster.recover()
