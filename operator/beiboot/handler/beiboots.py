import traceback
from asyncio import sleep

import click
import kopf

from beiboot.configuration import configuration
from beiboot.clusterstate import BeibootCluster


@kopf.on.resume("beiboot")
@kopf.on.create("beiboot")
async def beiboot_created(body, logger, **kwargs):
    """
    > If the cluster is not running, try to create it. If it is running, reconcile it

    :param body: The body of the Kubernetes resource that triggered the event
    :param logger: the logger object
    """
    parameters = configuration.refresh_k8s_config(body.get("parameters"))
    logger.debug(parameters)
    cluster = BeibootCluster(configuration, parameters, model=body, logger=logger)

    if cluster.is_requested or cluster.is_preparing or cluster.is_restoring or cluster.is_creating:
        # this is the initial process for a Beiboot
        try:
            if cluster.is_requested:
                await cluster.prepare()
            if cluster.is_preparing:
                logger.info("is_preparing")
                if cluster.model.get("fromShelf"):
                    logger.info("fromShelf -> restore")
                    await cluster.restore()
                else:
                    logger.info("not fromShelf -> create")
                    await cluster.create()
            if cluster.is_restoring:
                logger.info("is_restoring")
                await cluster.create()
            if cluster.is_creating:
                await cluster.boot()
        except kopf.TemporaryError as e:
            raise e from None
        except kopf.PermanentError as e:
            await cluster.impair(str(e))
            raise e from None
        except Exception as e:  # noqa
            logger.error(traceback.format_exc())
            logger.error(
                "Could not create cluster due to the following error: " + str(e)
            )
            await cluster.impair(str(e))
            raise kopf.PermanentError(str(e))

    if cluster.is_pending:
        try:
            await cluster.operate()  # become running
            await sleep(1)
        except kopf.PermanentError as e:
            await cluster.impair(str(e))
            raise e from None
    if cluster.is_running or (cluster.is_ready and await cluster.kubeconfig):
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


# this is a workaround to get the --dev flag from the CLI for testing
# https://kopf.readthedocs.io/en/stable/cli/#development-mode
try:
    _ctx = click.get_current_context()
    if "priority" in _ctx.params and _ctx.params["priority"] == 666:
        RECONCILIATION_INTERVAL = 2
    else:
        RECONCILIATION_INTERVAL = 60
except RuntimeError:
    # this module is not imported via kopf CLI
    RECONCILIATION_INTERVAL = 2


@kopf.timer("beiboot", interval=RECONCILIATION_INTERVAL)
async def reconcile_beiboot(body, logger, **kwargs):
    """
    If the cluster is running or ready, it calls the `reconcile` method on it

    :param body: The body of the Kubernetes resource that triggered the handler
    :param logger: a logger object
    """
    parameters = configuration.refresh_k8s_config(body.get("parameters"))
    cluster = BeibootCluster(configuration, parameters, model=body, logger=logger)

    if cluster.should_terminate:
        # terminate this cluster
        try:
            await cluster.terminate()
        except Exception as e:
            logger.error(e)
            raise kopf.PermanentError(e)

    if cluster.is_running or cluster.is_ready:
        try:
            await cluster.reconcile()
        except (kopf.PermanentError, kopf.TemporaryError) as e:
            await cluster.impair(str(e))
            raise e from None
    elif cluster.is_error:
        try:
            await cluster.recover()
        except (kopf.PermanentError, kopf.TemporaryError) as e:
            await cluster.impair(str(e))
            raise e from None


@kopf.on.delete("beiboot")
async def beiboot_deleted(body, logger, **kwargs):
    """
    It deletes the cluster if it's not REQUESTED state

    :param body: the body of the request
    :param logger: a logger object
    """
    parameters = configuration.refresh_k8s_config()
    cluster = BeibootCluster(configuration, parameters, model=body, logger=logger)
    if not cluster.is_requested:
        await cluster.terminate()
