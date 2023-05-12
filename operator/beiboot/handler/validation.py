import kopf
import kubernetes as k8s

from beiboot.configuration import configuration, ClusterConfiguration
from beiboot.utils import get_namespace_name, parse_timedelta

core_v1_api = k8s.client.CoreV1Api()
custom_api = k8s.client.CustomObjectsApi()


def validate_namespace(name: str, _: dict, defaults: ClusterConfiguration, logger):

    namespace = get_namespace_name(name, defaults)

    if len(namespace) > 63:
        raise kopf.AdmissionError(
            f"Namespace '{namespace}' is longer than 63 characters"
        )

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


def validate_session_timeout(
    name: str, parameters: dict, _: ClusterConfiguration, logger
):
    if mlt := parameters.get("maxSessionTimeout"):
        try:
            parse_timedelta(mlt)
        except ValueError as e:
            logger.warning(f"maxSessionTimeout parameter is not valid: {e}")
            raise kopf.AdmissionError(f"maxSessionTimeout parameter is not valid: {e}")


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


def validate_shelf(name: str, parameters: dict, defaults: ClusterConfiguration, logger):
    if shelf_name := parameters.get("fromShelf"):
        try:
            shelf = custom_api.get_namespaced_custom_object(
                group="beiboots.getdeck.dev",
                version="v1",
                namespace=configuration.NAMESPACE,
                plural="shelves",
                name=shelf_name,
            )
            if shelf.get("state") != "READY":
                raise kopf.AdmissionError(
                    f"Shelf for Beiboot '{shelf_name}' not ready: {shelf.get('state')}"
                )
        except k8s.client.exceptions.ApiException as e:
            logger.info(f"Shelf {shelf_name} handled with {e.reason}")
            raise kopf.AdmissionError(
                f"Shelf '{shelf_name}' for Beiboot '{name}' doesn't exist or has other issue: {e.reason}"
            )


VALIDATORS = [
    validate_namespace,
    validate_maxlifetime,
    validate_session_timeout,
    validate_shelf,
]


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

        shelf_name = body.get("fromShelf")
        if shelf_name:
            parameters["fromShelf"] = shelf_name

        for validator in VALIDATORS:
            validator(name, parameters, cluster_config, logger)
        return True
    else:
        return True


def validate_volume_snapshot_class(
    name: str, parameters: dict, defaults: ClusterConfiguration, logger
):
    """
    Validate that the volumeSnapshotClass exists.
    """
    if class_name := parameters.get("volumeSnapshotClass"):
        try:
            _ = custom_api.get_cluster_custom_object(
                group="snapshot.storage.k8s.io",
                version="v1",
                plural="volumesnapshotclasses",
                name=name,
            )
        except k8s.client.exceptions.ApiException as e:
            logger.info(f"Shelf {name} handled with {e.reason}")
            raise kopf.AdmissionError(
                f"VolumeSnapshotClass '{class_name}' for Beiboot '{name}' doesn't exist or has other issue: {e.reason}"
            )


def validate_shelf_cluster(
    name: str, parameters: dict, defaults: ClusterConfiguration, logger
):
    """
    Validate that the cluster that is to be shelved exists (Beiboot CRD and namespace).
    """
    cluster_name = parameters.get("clusterName")
    cluster_namespace = parameters.get("clusterNamespace")
    try:
        bbt = custom_api.get_namespaced_custom_object(
            group="getdeck.dev",
            version="v1",
            namespace=configuration.NAMESPACE,
            plural="beiboots",
            name=cluster_name,
        )
        if bbt.get("state") != "READY":
            raise kopf.AdmissionError(
                f"Beiboot '{cluster_name}' for Shelf '{name}' not ready: {bbt.get('state')}"
            )
    except k8s.client.exceptions.ApiException as e:
        logger.info(f"Shelf {name} handled with {e.reason}")
        raise kopf.AdmissionError(
            f"Beiboot '{cluster_name}' for Shelf '{name}' doesn't exist or has other issue: {e.reason}"
        )

    try:
        _ = core_v1_api.read_namespace(name=cluster_namespace)
    except k8s.client.exceptions.ApiException as e:
        logger.info(f"Shelf {name} handled with {e.reason}")
        raise kopf.AdmissionError(
            f"Namespace '{cluster_namespace}' of Beiboot '{cluster_name}' for Shelf '{cluster_name}' doesn't exist or "
            f"has other issue: {e.reason}"
        )


SHELF_VALIDATORS = [validate_volume_snapshot_class, validate_shelf_cluster]


@kopf.on.validate("shelf.beiboots.getdeck.dev", id="validate-shelf")  # type: ignore
def check_validate_shelf_request(body, logger, operation, **_):
    """
    If the operation is a CREATE, validate the specs of the Shelf given by the client. If it cannot successfully
    validate, raise error.

    :param body: The body of the request
    :param logger: A logger object that can be used to log messages
    :param operation: The operation that is being performed on the resource
    :return: True
    """
    logger.info("Validating Shelf request")

    if operation == "CREATE":
        cluster_config = configuration.refresh_k8s_config()
        name = body.get("metadata").get("name")
        cluster_name = body.get("clusterName")
        cluster_namespace = body.get("clusterNamespace")
        volume_snapshot_class = body.get("volumeSnapshotClass")
        parameters = {
            "clusterName": cluster_name,
            "clusterNamespace": cluster_namespace,
            "volumeSnapshotClass": volume_snapshot_class,
        }

        for validator in SHELF_VALIDATORS:
            validator(name, parameters, cluster_config, logger)
        return True
    else:
        return True
