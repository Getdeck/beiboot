import kopf
import kubernetes as k8s

from beiboot.configuration import configuration
from beiboot.utils import get_namespace_name

core_v1_api = k8s.client.CoreV1Api()


@kopf.on.validate("beiboot.getdeck.dev", id="check-namespace-ready")
def check_namespace_ready(body, logger, operation, **_):
    cluster_config = configuration.refresh_k8s_config()
    name = body.get("metadata").get("name")
    namespace = get_namespace_name(name, cluster_config)
    logger.info(f"Validating namespace for operation {operation}")

    if operation == "CREATE":
        try:
            ns = core_v1_api.read_namespace(namespace)
            logger.warn(f"Namespace {ns.metadata.name} exists")
            raise kopf.AdmissionError(
                f"Namespace for Beiboot '{namespace}' not ready: {ns.status.phase}"
            )
        except k8s.client.exceptions.ApiException as e:
            logger.info(f"Namespace {namespace} handled with {e.reason}")
            if e.status != 404:
                raise kopf.AdmissionError(
                    f"Namespace for Beiboot '{namespace}' not ready: {e.reason}"
                )
            else:
                pass
        return True
    else:
        return True
