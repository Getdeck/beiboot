import traceback

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
    logger.info(f"shelf_created body: {body}")
    configuration = ShelfConfiguration()
    shelf = Shelf(configuration, model=body, logger=logger)

    if shelf.is_requested:
        # get beiboot cluster from beiboot CRD to determine provider and get PVC names
        bbt = get_beiboot_by_name(body["clusterName"], api_instance=objects_api, namespace=configuration.NAMESPACE)
        bbt = Body(bbt)
        parameters = bbt_configuration.refresh_k8s_config(body.get("parameters"))
        logger.debug(parameters)
        cluster = BeibootCluster(bbt_configuration, parameters, model=bbt, logger=logger)
        logger.info(f"cluster.configuration: {cluster.configuration}")
        logger.info(f"cluster.parameters: {cluster.parameters}")
        logger.info(f"cluster.model: {cluster.model}")
        pvcs = await cluster.provider.get_pvc_mapping()
        shelf.set_persistent_volume_claims(pvcs)
        # figure out whether volumeSnapshotClass needs to be set and to which value
        if not shelf.volume_snapshot_class:
            configmap_name = cluster.configuration.CONFIGMAP_NAME
            configmap = core_api.read_namespaced_config_map(
                name=configmap_name,
                namespace=cluster.configuration.NAMESPACE
            )
            shelf.set_volume_snapshot_class(configmap.data["shelfStorageClass"])

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
        logger.info("shelf.is_creating")
        logger.info(f"shelf state before shelve(): {shelf.current_state}")
        await shelf.shelve()
        logger.info(f"shelf state after shelve(): {shelf.current_state}")

    if shelf.is_pending:
        logger.info(f"shelf state before reconcile(): {shelf.current_state}")
        logger.info("shelf.is_pending")
        # await shelf.reconcile()
        logger.info(f"shelf state after reconcile(): {shelf.current_state}")

    if shelf.is_ready:
        logger.info("shelf.is_ready")

    if shelf.is_error:
        logger.info("shelf.is_error")

    if shelf.is_terminating:
        logger.info("shelf.is_terminating")
