import traceback
from asyncio import sleep

import kubernetes as k8s
import kopf
from kopf import Body

from beiboot.clusterstate import BeibootCluster
from beiboot.configuration import ShelfConfiguration, configuration as bbt_configuration
from beiboot.shelfstate import Shelf
from beiboot.utils import get_beiboot_by_name

core_api = k8s.client.CoreV1Api()
objects_api = k8s.client.CustomObjectsApi()


@kopf.on.resume("shelf")
@kopf.on.create("shelf")
async def shelf_created(body, logger, **kwargs):
    """

    :param body: The body of the Kubernetes resource that triggered the event
    :param logger: the logger object
    """
    configuration = ShelfConfiguration()
    shelf = Shelf(configuration, model=body, logger=logger)

    if shelf.is_requested:
        # get beiboot cluster from beiboot CRD to determine provider and get PVC names
        bbt = get_beiboot_by_name(body["clusterName"], api_instance=objects_api, namespace=configuration.NAMESPACE)
        bbt = Body(bbt)
        parameters = bbt_configuration.refresh_k8s_config(body.get("parameters"))
        logger.debug(parameters)
        cluster = BeibootCluster(bbt_configuration, parameters, model=bbt, logger=logger)
        pvcs = await cluster.provider.get_pvc_mapping()
        shelf.set_persistent_volume_claims(pvcs)
        shelf.set_cluster_namespace(cluster.namespace)
        # figure out whether volumeSnapshotClass needs to be set and to which value
        if not shelf.volume_snapshot_class:
            configmap_name = cluster.configuration.CONFIGMAP_NAME
            configmap = core_api.read_namespaced_config_map(
                name=configmap_name,
                namespace=cluster.configuration.NAMESPACE
            )
            if not configmap.data["shelfStorageClass"]:
                error_msg = f"Neither volumeSnapshotClass is set on shelf CRD '{shelf.name}, nor shelfStorageClass " \
                            f"is configured for beiboot cluster {cluster.name}"
                shelf.impair(error_msg)
                raise kopf.PermanentError(error_msg)
            shelf.set_cluster_default_volume_snapshot_class(configmap.data["shelfStorageClass"])

        try:
            await shelf.create()
        except kopf.PermanentError as e:
            await shelf.impair(str(e))
            raise e from None
        except Exception as e:  # noqa
            logger.error(traceback.format_exc())
            logger.error(
                "Could not create shelf due to the following error: " + str(e)
            )
            await cluster.impair(str(e))
            raise kopf.PermanentError(str(e))

    if shelf.is_creating:
        try:
            await shelf.shelve()
        except kopf.PermanentError as e:
            await shelf.impair(str(e))
            raise e from None
        except Exception as e:  # noqa
            logger.error(traceback.format_exc())
            logger.error(
                "Could not create shelf due to the following error: " + str(e)
            )
            await shelf.impair(str(e))
            raise kopf.PermanentError(str(e))

    if shelf.is_pending:
        try:
            await shelf.operate()
            await sleep(1)
        except kopf.PermanentError as e:
            await shelf.impair(str(e))
            raise e from None

    if shelf.is_ready:
        logger.info("shelf.is_ready")
        await shelf.reconcile()
    elif shelf.is_error:
        logger.info("shelf.is_error")
        await shelf.reconcile()


@kopf.on.delete("shelf")
async def shelf_deleted(body, logger, **kwargs):
    """
    It deletes the shelf if it's not REQUESTED state

    :param body: thh body of the request
    :param logger: a logger object
    """
    configuration = ShelfConfiguration()
    shelf = Shelf(configuration, model=body, logger=logger)
    if not shelf.is_requested:
        await shelf.terminate()
