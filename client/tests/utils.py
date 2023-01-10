def create_beiboot_object(name: str, parameters: dict, labels: dict = {}):
    import kubernetes as k8s

    custom_api = k8s.client.CustomObjectsApi()

    bbt = {
        "apiVersion": "getdeck.dev/v1",
        "kind": "beiboot",
        "provider": "k3s",
        "metadata": {"name": name, "namespace": "getdeck", "labels": labels},
        "parameters": parameters,
    }
    custom_api.create_namespaced_custom_object(
        namespace="getdeck",
        body=bbt,
        group="getdeck.dev",
        plural="beiboots",
        version="v1",
    )
