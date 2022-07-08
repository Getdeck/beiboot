import logging

import kubernetes as k8s

from beiboot.resources.crds import create_beiboot_definition

logger = logging.getLogger("beiboot")

app = k8s.client.AppsV1Api()
core_v1_api = k8s.client.CoreV1Api()
rbac_api = k8s.client.RbacAuthorizationV1Api()
extension_api = k8s.client.ApiextensionsV1Api()
custom_api = k8s.client.CustomObjectsApi()


def purge_operator():
    """
    Purge Beiboot and all related components from the cluster; let Beiboot handle deletion of beiboots (CRD)
    :return:
    """
    bbt = create_beiboot_definition()

    remove_crd(bbt)


def remove_crd(bbt: k8s.client.V1CustomResourceDefinition):
    logger.info("Removing CRD Beiboots")
    try:
        extension_api.delete_custom_resource_definition(name=bbt.metadata.name)
    except k8s.client.exceptions.ApiException as e:
        logger.error("Error removing CRD Beiboots: " + str(e))


if __name__ == "__main__":
    try:
        k8s.config.load_incluster_config()
        logger.info("Loaded in-cluster config")
    except k8s.config.ConfigException:
        # if the operator is executed locally load the current KUBECONFIG
        k8s.config.load_kube_config()
        logger.info("Loaded KUBECONFIG config")
    purge_operator()
