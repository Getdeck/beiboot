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
        default_factory=lambda: {"app": "beiboot", "beiboot.dev/is-node": "true", "beiboot.dev/is-server": "true"}
    )
    serverResources: dict = field(
        default_factory=lambda: {
            "requests": {"cpu": "1", "memory": "512Mi"},
            "limits": {},
        }
    )
    serverStorageRequests: str = field(default_factory=lambda: "2Gi")
    nodeResources: dict = field(
        default_factory=lambda: {
            "requests": {"cpu": "0.5", "memory": "512Mi"},
            "limits": {"cpu": "1", "memory": "1024Mi"},
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
            "ports": "31820-31920",
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
                    logger.warning(f"The configuration value for '{k}' is not valid.")
        return _s


class BeibootConfiguration:
    def refresh_k8s_config(self) -> ClusterConfiguration:
        from beiboot.resources.configmaps import create_beiboot_configmap

        core_v1_api = k8s.client.CoreV1Api()
        try:
            configmap = core_v1_api.read_namespaced_config_map(
                name=self.CONFIGMAP_NAME, namespace=self.NAMESPACE
            )
            logger.info("Beiboot configmap exists; loading it")
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
                    logger.error(f"Cannot create configmap for Beiboot: {e.reason}")
            else:
                raise e
        return ClusterConfiguration.decode_cluster_configuration(configmap)

    def __init__(self):
        self.NAMESPACE = config("BEIBOOT_NAMESPACE", default="getdeck")
        self.CONFIGMAP_NAME = config("BEIBOOT_CONFIGMAP", default="beiboot-config")
        self._cluster_config = None

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if k.isupper()}

    def __str__(self):
        return str(self.to_dict())


configuration = BeibootConfiguration()
