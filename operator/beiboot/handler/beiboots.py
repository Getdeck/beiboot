import traceback

import kopf

from beiboot.configuration import configuration
from beiboot.clusterstate import BeibootCluster
from beiboot.resources.utils import handle_delete_namespace


@kopf.on.create("beiboot")
async def beiboot_created(body, logger, **kwargs):
    parameters = configuration.refresh_k8s_config()
    cluster = BeibootCluster(configuration, parameters, model=body, logger=logger)

    try:
        await cluster.create()
        await cluster.watch()
        await cluster.operate()
    except kopf.PermanentError as e:
        await cluster.impair(str(e))
        raise e
    except Exception as e:  # noqa
        logger.error(traceback.format_exc())
        logger.error("Could not create cluster due to the following error: " + str(e))
        await cluster.impair(str(e))


@kopf.on.delete("beiboot")
async def beiboot_deleted(body, logger, **kwargs):
    parameters = configuration.refresh_k8s_config()
    cluster = BeibootCluster(configuration, parameters, model=body, logger=logger)
    await cluster.terminate()
    handle_delete_namespace(logger, cluster.namespace)
