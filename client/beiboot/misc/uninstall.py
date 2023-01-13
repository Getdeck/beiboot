import kubernetes as k8s

from beiboot.configuration import ClientConfiguration
from beiboot import api


def remove_all_beiboots(config: ClientConfiguration):
    bbts = api.read_all(config=config)
    for bbt in bbts:
        api.delete(bbt)


def remove_remainder_beiboot_namespaces(config: ClientConfiguration):
    try:
        configmap = config.K8S_CORE_API.read_namespaced_config_map(
            name=config.CONFIGMAP_NAME, namespace=config.NAMESPACE
        )
    except k8s.client.exceptions.ApiException:  # type: ignore
        return []
    if "namespacePrefix" not in configmap.data:  # type: ignore
        return []
    namespace_prefix = configmap.data["namespacePrefix"]  # type: ignore
    namespaces = config.K8S_CORE_API.list_namespace()
    removed_namespaces = []
    for ns in namespaces.items:
        if ns.metadata.name.startswith(namespace_prefix):
            removed_namespaces.append(ns.metadata.name)
    return removed_namespaces


def remove_remainder_bbts(config: ClientConfiguration):
    try:
        bbts = config.K8S_CUSTOM_OBJECT_API.list_namespaced_custom_object(
            group="getdeck.dev",
            version="v1",
            namespace=config.NAMESPACE,
            plural="beiboots",
        )
    except Exception:
        return None
    for bbt in bbts.get("items"):
        try:
            config.K8S_CUSTOM_OBJECT_API.patch_namespaced_custom_object(
                group="getdeck.dev",
                version="v1",
                plural="beiboots",
                namespace=config.NAMESPACE,
                name=bbt["metadata"]["name"],
                body={"metadata": {"finalizers": None}},
            )
            config.K8S_CUSTOM_OBJECT_API.delete_namespaced_custom_object(
                group="getdeck.dev",
                version="v1",
                plural="beiboots",
                namespace=config.NAMESPACE,
                name=bbt["metadata"]["name"],
            )
        except Exception:
            continue
    return None


def remove_beiboot_crds(config: ClientConfiguration):
    try:
        config.K8S_EXTENSIONS_API.delete_custom_resource_definition(
            name="beiboots.getdeck.dev"
        )
    except k8s.client.exceptions.ApiException as e:  # type: ignore
        if e.status == 404:
            return
        else:
            raise e from None
    try:
        config.K8S_EXTENSIONS_API.delete_custom_resource_definition(
            name="shelves.beiboots.getdeck.dev"
        )
    except k8s.client.exceptions.ApiException as e:  # type: ignore
        if e.status == 404:
            return
        else:
            raise e from None


def remove_beiboot_rbac(config: ClientConfiguration):
    try:
        config.K8S_RBAC_API.delete_cluster_role_binding(name="getdeck-beiboot-operator")
    except k8s.client.exceptions.ApiException as e:  # type: ignore
        if e.status == 404:
            pass
        else:
            raise e from None
    try:
        config.K8S_RBAC_API.delete_cluster_role(name="getdeck:beiboot:operator")
    except k8s.client.exceptions.ApiException as e:  # type: ignore
        if e.status == 404:
            pass
        else:
            raise e from None


def remove_beiboot_webhooks(config: ClientConfiguration):
    try:
        config.K8S_ADMISSION_API.delete_validating_webhook_configuration(
            name="beiboot.getdeck.dev"
        )
    except k8s.client.exceptions.ApiException as e:  # type: ignore
        if e.status == 404:
            pass
        else:
            raise e from None


def remove_beiboot_namespace(config: ClientConfiguration):
    try:
        config.K8S_CORE_API.delete_namespace(name=config.NAMESPACE)
    except k8s.client.exceptions.ApiException as e:  # type: ignore
        if e.status == 404:
            return
        else:
            raise e from None
