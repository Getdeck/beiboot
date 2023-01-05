from beiboot.types import InstallOptions


def data(params: InstallOptions) -> list[dict]:
    return [
        {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": "beiboot-config",
                "namespace": params.namespace,
            },
            "data": {
                "clusterReadyTimeout": "180",
                "gefyra": '{"enabled": true, "endpoint": null}',
                "k8sVersion": "null",
                "maxLifetime": "null",
                "maxSessionTimeout": "null",
                "namespacePrefix": "getdeck-bbt",
                "nodeLabels": '{"app": "beiboot", "beiboot.dev/is-node": "true"}',
                "nodeResources": '{"requests": {"cpu": "1", "memory": "1Gi"}, "limits": {}}',
                "nodeStorageRequests": "1Gi",
                "nodes": "1",
                "ports": "null",
                "serverLabels": '{"app": "beiboot", "beiboot.dev/is-node": "true", "beiboot.dev/is-server": "true"}',
                "serverResources": '{"requests": {"cpu": "1", "memory": "1Gi"}, "limits": {}}',
                "serverStartupTimeout": "60",
                "serverStorageRequests": "1Gi",
                "tunnel": '{"enabled": true, "endpoint": null}',
                "storageClass": params.storage_class,
                "shelfStorageClass": params.shelf_storage_class,
            },
        }
    ]
