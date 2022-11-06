import logging

import kopf


@kopf.on.startup()
def configure(settings: kopf.OperatorSettings, **_):
    settings.peering.standalone = True
    settings.posting.level = logging.INFO
    settings.posting.enabled = False
    settings.execution.max_workers = 10
    settings.persistence.diffbase_storage = kopf.AnnotationsDiffBaseStorage(
        prefix="getdeck.dev",
        key="last-handled-configuration",
    )
    settings.persistence.finalizer = "beiboot.getdeck.dev/kopf-finalizer"
    settings.admission.server = kopf.WebhookServer(
        port=9443,
        certfile="client-cert.pem",
        pkeyfile="client-key.pem",
        host="beiboot-admission.getdeck.svc",
    )
