import logging

import kopf


@kopf.on.startup()
def configure(settings: kopf.OperatorSettings, **_):
    settings.peering.standalone = True
    settings.posting.level = logging.INFO
    settings.persistence.diffbase_storage = kopf.AnnotationsDiffBaseStorage(
        prefix="getdeck.dev",
        key="last-handled-configuration",
    )
    settings.persistence.finalizer = "beiboot.getdeck.dev/kopf-finalizer"
