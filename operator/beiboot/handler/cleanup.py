import kopf


@kopf.on.cleanup()
def remove_everything(logger, **kwargs):
    logger.info("Beiboot shutdown requested")
