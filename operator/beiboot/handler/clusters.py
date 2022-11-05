import kopf


@kopf.on.event("pods")
async def handle_all_pods(**_):
    pass


async def handle_cluster_pod_events(body, logger, **kwargs):
    logger.info(f"something has happend to: {body}")
