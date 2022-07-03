import kubernetes as k8s
from kubernetes.client import CustomObjectsApi


if __name__ == "__main__":
    k8s.config.load_kube_config()
    namespace = "getdeck"
    name = "my-cluster-1"
    bbt = CustomObjectsApi().delete_namespaced_custom_object(
        namespace=namespace,
        name=name,
        group="getdeck.dev",
        plural="beiboots",
        version="v1",
    )
