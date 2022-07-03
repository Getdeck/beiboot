import kopf

from beiboot.purge import purge_operator


@kopf.on.cleanup()
def remove_everything(logger, **kwargs):
    logger.info("Beiboot shutdown requested")
    try:
        purge_operator()
    except Exception as e:
        logger.exception(e)
