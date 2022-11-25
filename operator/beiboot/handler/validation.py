import kopf
import kubernetes as k8s

from beiboot.configuration import configuration, ClusterConfiguration
from beiboot.utils import get_namespace_name, parse_timedelta


def validate_namespace(name: str, _: dict, defaults: ClusterConfiguration, logger):
    core_v1_api = k8s.client.CoreV1Api()

    namespace = get_namespace_name(name, defaults)
    try:
        ns = core_v1_api.read_namespace(namespace)
        logger.warning(f"Namespace {ns.metadata.name} exists")
        raise kopf.AdmissionError(
            f"Namespace for Beiboot '{namespace}' not ready: {ns.status.phase}"
        )
    except k8s.client.exceptions.ApiException as e:
        logger.info(f"Namespace {namespace} handled with {e.reason}")
        if e.status != 404:
            raise kopf.AdmissionError(
                f"Namespace for Beiboot '{namespace}' not ready: {e.reason}"
            )


def validate_maxlifetime(name: str, parameters: dict, _: ClusterConfiguration, logger):
    if mlt := parameters.get("maxLifetime"):
        try:
            parse_timedelta(mlt)
        except ValueError as e:
            logger.warning(f"maxLifetime parameter is not valid: {e}")
            raise kopf.AdmissionError(f"maxLifetime parameter is not valid: {e}")


def validate_ports(name: str, parameters: dict, _: ClusterConfiguration, logger):
    if ports := parameters.get("ports"):
        try:
            if type(ports) != list:
                raise ValueError("ports is not of type list")
            for port_mapping in ports:
                s, t = port_mapping.split(":")
                if int(s) > 65535 or int(s) <= 0:
                    raise ValueError(f"The port {s} is not in range 1-65535")
                if int(t) > 65535 or int(t) <= 0:
                    raise ValueError(f"The port {t} is not in range 1-65535")

        except Exception as e:
            logger.warning(f"ports parameter is not valid: {e}")
            raise kopf.AdmissionError(f"ports parameter is not valid: {e}")


VALIDATORS = [validate_namespace, validate_maxlifetime]


@kopf.on.validate("beiboot.getdeck.dev", id="validate-parameters")  # type: ignore
def check_validate_beiboot_request(body, logger, operation, **_):
    """
    If the operation is a CREATE, validate the parameters given by the client. If it cannot successfully validate,
    raise error.

    :param body: The body of the request
    :param logger: A logger object that can be used to log messages
    :param operation: The operation that is being performed on the resource
    :return: True
    """
    logger.info("Validating parameters for requested Beiboot")

    if operation == "CREATE":
        cluster_config = configuration.refresh_k8s_config()
        name = body.get("metadata").get("name")
        parameters = body.get("parameters")

        for validator in VALIDATORS:
            validator(name, parameters, cluster_config, logger)
        return True
    else:
        return True
