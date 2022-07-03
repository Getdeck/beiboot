from decouple import config


class BeibootConfiguration:
    def __init__(self):
        self.NAMESPACE = config("BEIBOOT_NAMESPACE", default="getdeck")
        self.CLUSTER_NAMESPACE_PREFIX = config(
            "BEIBOOT_NAMESPACE_PREFIX", default="getdeck-bbt"
        )
        self.API_SERVER_STARTUP_TIMEOUT = config(
            "BEIBOOT_API_SERVER_STARTUP_TIMEOUT", default=30, cast=int
        )
        self.API_SERVER_CONTAINER_NAME = config(
            "BEIBOOT_API_SERVER_CONTAINER_NAME", default="apiserver"
        )
        self.KUBECONFIG_LOCATION = config(
            "BEIBOOT_KUBECONFIG_LOCATION", default="/getdeck/kube-config.yaml"
        )
        self.KUBECONFIG_TIMEOUT = config(
            "BEIBOOT_KUBECONFIG_TIMEOUT", default=30, cast=int
        )

        #
        # k3s settings
        #
        self.K3S_IMAGE = config("BEIBOOT_K3S_IMAGE", default="rancher/k3s")
        self.K3S_IMAGE_TAG = config("BEIBOOT_K3S_IMAGE_TAG", default="v1.24.2-rc1-k3s1")
        self.K3S_IMAGE_PULLPOLICY = config(
            "BEIBOOT_K3S_IMAGE_PULLPOLICY", default="IfNotPresent"
        )

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if k.isupper()}

    def __str__(self):
        return str(self.to_dict())


configuration = BeibootConfiguration()
