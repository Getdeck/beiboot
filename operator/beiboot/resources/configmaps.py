import kubernetes as k8s

from beiboot.configuration import configuration


def create_beiboot_configmap(data: dict) -> k8s.client.V1ConfigMap:
    configmap = k8s.client.V1ConfigMap(
        api_version="v1",
        kind="ConfigMap",
        data=data,
        metadata=k8s.client.V1ObjectMeta(
            name=configuration.CONFIGMAP_NAME,
            namespace=configuration.NAMESPACE,
        ),
    )
    return configmap
