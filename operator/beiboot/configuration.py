import logging
from dataclasses import dataclass, fields, field
from json import JSONDecodeError

from decouple import config
import json
import kubernetes as k8s


logger = logging.getLogger("beiboot")


@dataclass
class ClusterConfiguration:
    nodes: int = field(default_factory=lambda: 2)
    nodeLabels: dict = field(
        default_factory=lambda: {"app": "beiboot", "beiboot.dev/is-node": "true"}
    )
    serverLabels: dict = field(
        default_factory=lambda: {
            "app": "beiboot",
            "beiboot.dev/is-node": "true",
            "beiboot.dev/is-server": "true",
        }
    )
    serverResources: dict = field(
        default_factory=lambda: {
            "requests": {"cpu": "1", "memory": "1Gi"},
            "limits": {},
        }
    )
    serverStorageRequests: str = field(default_factory=lambda: "10Gi")
    nodeResources: dict = field(
        default_factory=lambda: {
            "requests": {"cpu": "1", "memory": "1Gi"},
            "limits": {},
        }
    )
    nodeStorageRequests: str = field(default_factory=lambda: "10Gi")
    namespacePrefix: str = field(default_factory=lambda: "getdeck-bbt")
    serverStartupTimeout: int = field(default_factory=lambda: 60)
    apiServerContainerName: str = field(default_factory=lambda: "apiserver")
    kubeconfigFromLocation: str = field(
        default_factory=lambda: "/getdeck/kube-config.yaml"
    )
    clusterReadyTimeout: int = field(default_factory=lambda: 180)
    # Gefyra integration
    gefyra: dict = field(
        default_factory=lambda: {
            "enabled": True,
            "endpoint": None,
        }
    )
    tunnel: dict = field(
        default_factory=lambda: {
            "enabled": True,
            "endpoint": None,
        }
    )
    # k3s settings
    k3sImage: str = field(default_factory=lambda: "rancher/k3s")
    k3sImageTag: str = field(default_factory=lambda: "v1.24.3-k3s1")
    k3sImagePullPolicy: str = field(default_factory=lambda: "IfNotPresent")

    def encode_cluster_configuration(self) -> dict:
        _s = {}
        for _field in fields(self):
            if type(getattr(self, _field.name)) in [int, float]:
                _s[str(_field.name)] = str(getattr(self, _field.name))
            if type(getattr(self, _field.name)) is str:
                _s[str(_field.name)] = getattr(self, _field.name)
            else:
                _s[str(_field.name)] = json.dumps(getattr(self, _field.name))
        return _s

    @classmethod
    def decode_cluster_configuration(cls, configmap: k8s.client.V1ConfigMap):
        _s = cls()
        field_names = [field.name for field in fields(_s)]
        for k, v in configmap.data.items():
            if k not in field_names:
                logger.warning(f"The configuration key '{k}' is unknown.")
            else:
                try:
                    setattr(_s, k, json.loads(v))
                except JSONDecodeError:
                    setattr(_s, k, v)
        return _s


class BeibootConfiguration:
    def refresh_k8s_config(self) -> ClusterConfiguration:
        from beiboot.resources.configmaps import create_beiboot_configmap

        core_v1_api = k8s.client.CoreV1Api()
        try:
            configmap = core_v1_api.read_namespaced_config_map(
                name=self.CONFIGMAP_NAME, namespace=self.NAMESPACE
            )
            logger.debug("Beiboot configmap exists; loading it")
        except k8s.client.exceptions.ApiException as e:
            if e.status == 404:
                logger.info("Beiboot configmap does not exist; creating it now")
                #  this does not exist
                configmap = create_beiboot_configmap(
                    ClusterConfiguration().encode_cluster_configuration()
                )
                try:
                    core_v1_api.create_namespaced_config_map(
                        namespace=self.NAMESPACE, body=configmap
                    )
                except k8s.client.exceptions.ApiException as e:
                    logger.error(e)
                    logger.error(f"Cannot create configmap for Beiboot: {e.reason}")
            else:
                raise e
        return ClusterConfiguration.decode_cluster_configuration(configmap)

    def __init__(self):
        self.NAMESPACE = config("BEIBOOT_NAMESPACE", default="getdeck")
        self.CONFIGMAP_NAME = config("BEIBOOT_CONFIGMAP", default="beiboot-config")
        self.GHOSTUNNEL_IMAGE = "ghostunnel/ghostunnel:v1.7.0"
        self.CERTSTRAP_IMAGE = "squareup/certstrap:1.3.0"
        self._cluster_config = None

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if k.isupper()}

    def __str__(self):
        return str(self.to_dict())


configuration = BeibootConfiguration()
