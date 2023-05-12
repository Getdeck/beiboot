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
                "maxLifetime": params.max_lifetime,
                "maxSessionTimeout": params.max_session_timeout,
                "namespacePrefix": params.namespace_prefix,
                "nodeLabels": '{"app": "beiboot", "beiboot.getdeck.dev/is-node": "true"}',
                "nodeResources": f'{{"requests": {{"cpu": "{params.node_requests_cpu}", "memory": "{params.node_requests_memory}"}}, "limits": {{}}}}',  # noqa
                "nodeStorageRequests": params.node_storage_request,
                "nodes": params.nodes,
                "ports": "null",
                "serverLabels": '{"app": "beiboot", "beiboot.getdeck.dev/is-node": "true", "beiboot.getdeck.dev/is-server": "true"}',  # noqa
                "serverResources": f'{{"requests": {{"cpu": "{params.server_requests_cpu}", "memory": "{params.server_requests_memory}"}}, "limits": {{}}}}',  # noqa
                "serverStartupTimeout": "60",
                "serverStorageRequests": params.server_storage_request,
                "tunnel": '{"enabled": true, "endpoint": null}',
                "storageClass": params.storage_class,
                "shelfStorageClass": params.shelf_storage_class,
            },
        }
    ]
