import kubernetes as k8s
from kubernetes.client import CustomObjectsApi


def create_k3s_beiboot(name="my-cluster", namespace="getdeck"):
    return {
        "apiVersion": "getdeck.dev/v1",
        "kind": "beiboot",
        "provider": "k3s",
        "metadata": {
            "name": name,
            "namespace": namespace,
        },
    }


if __name__ == "__main__":
    k8s.config.load_kube_config()
    namespace = "getdeck"
    name = "my-cluster"
    i = 1
    api = CustomObjectsApi()
    while i < 10:
        try:
            api.get_namespaced_custom_object(
                namespace=namespace,
                name=f"{name}-{i}",
                group="getdeck.dev",
                plural="beiboots",
                version="v1",
            )
            i = i + 1
            continue
        except:
            body = create_k3s_beiboot(f"{name}-{i}", namespace)
            bbt = api.create_namespaced_custom_object(
                namespace=namespace,
                body=body,
                group="getdeck.dev",
                plural="beiboots",
                version="v1",
            )
            break
