import kopf
import kubernetes as k8s

from beiboot.resources.crds import create_beiboot_definition

app = k8s.client.AppsV1Api()
core_v1_api = k8s.client.CoreV1Api()
extension_api = k8s.client.ApiextensionsV1Api()
events = k8s.client.EventsV1Api()


def handle_crds(logger) -> k8s.client.V1CustomResourceDefinition:
    """
    It creates a custom resource definition for the Beiboot resource

    :param logger: a logger object
    :return: The CRD definition
    """
    bbt_def = create_beiboot_definition()
    try:
        extension_api.create_custom_resource_definition(body=bbt_def)
        logger.info("Beiboot CRD created")
    except k8s.client.exceptions.ApiException as e:
        if e.status == 409:
            logger.warning("Beiboot CRD already available")
        else:
            raise e
    return bbt_def


@kopf.on.startup()
async def check_beiboot_components(logger, **kwargs) -> None:
    """
    Checks all required components of Beiboot in the current version. This handler installs components if they are
    not already available with the matching configuration.
    """
    from beiboot.configuration import configuration

    logger.info(
        f"Ensuring Beiboot components with the following configuration: {configuration}"
    )

    #
    # handle Beiboot CRDs and Permissions
    #
    handle_crds(logger)

    #
    # handle Beiboot configuration configmap
    #
    configuration.refresh_k8s_config()

    logger.info("Beiboot components installed/patched")
