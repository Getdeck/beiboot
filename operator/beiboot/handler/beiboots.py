import traceback

import kopf

from beiboot.configuration import configuration
from beiboot.clusterstate import BeibootCluster
from beiboot.resources.utils import handle_delete_namespace


@kopf.on.resume("beiboot")
@kopf.on.create("beiboot")
async def beiboot_created(body, logger, **kwargs):
    parameters = configuration.refresh_k8s_config()
    cluster = BeibootCluster(configuration, parameters, model=body, logger=logger)

    if cluster.is_requested:
        # this is the initial process for a Beiboot
        try:
            await cluster.create()
            if cluster.is_creating:
                await cluster.boot()
            if cluster.is_pending:
                await cluster.operate()
        except kopf.PermanentError as e:
            await cluster.impair(str(e))
            raise e from None
        except kopf.TemporaryError as e:
            await cluster.impair(str(e))
            raise e from None
        except Exception as e:  # noqa
            logger.error(traceback.format_exc())
            logger.error(
                "Could not create cluster due to the following error: " + str(e)
            )
            await cluster.impair(str(e))
            raise kopf.PermanentError(str(e))
    elif cluster.is_running or (cluster.is_ready and await cluster.kubeconfig):
        # if this cluster is already running, we continue
        await cluster.reconcile()
    elif cluster.is_error:
        # here are the retries and error state handled from a run before
        # try again if there was an error creating the cluster (which might be a temporary problem)
        if not cluster.completed_transition(BeibootCluster.pending.value):
            try:
                await cluster.create()
                if cluster.is_creating:
                    await cluster.boot()
                if cluster.is_pending:
                    await cluster.operate()
            except kopf.TemporaryError as e:
                await cluster.impair(str(e))
                raise e from None
        elif cluster.completed_transition(BeibootCluster.running.value):
            try:
                await cluster.reconcile()
            except (kopf.PermanentError, kopf.TemporaryError) as e:
                await cluster.impair(str(e))
                raise e from None
            except Exception as e:
                await cluster.impair(str(e))
                raise e from None


@kopf.timer("beiboot", interval=60)
async def reconcile_beiboot(body, logger, **kwargs):
    parameters = configuration.refresh_k8s_config()
    cluster = BeibootCluster(configuration, parameters, model=body, logger=logger)

    if cluster.is_running or cluster.is_ready:
        try:
            await cluster.reconcile()
        except (kopf.PermanentError, kopf.TemporaryError) as e:
            await cluster.impair(str(e))
            raise e from None


@kopf.on.delete("beiboot")
async def beiboot_deleted(body, logger, **kwargs):
    parameters = configuration.refresh_k8s_config()
    cluster = BeibootCluster(configuration, parameters, model=body, logger=logger)
    await cluster.terminate()
    handle_delete_namespace(logger, cluster.namespace)
