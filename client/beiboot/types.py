import kubernetes as k8s

from dataclasses import dataclass, field, fields
from enum import Enum
from typing import Optional, Any

from beiboot.configuration import default_configuration, ClientConfiguration


class BeibootProvider(Enum):
    K3S = "k3s"


@dataclass
class GefyraParams:
    # deploy Gefyra components to this Beiboot
    enabled: bool = field(default_factory=lambda: True)
    # endpoint written to the kubeconfig for Gefyra
    endpoint: Optional[str] = field(default_factory=lambda: None)


@dataclass
class BeibootParameters:
    # the ports mapped to local host
    ports: Optional[list[str]] = field(default_factory=lambda: None)
    # amount of nodes for this cluster
    nodes: Optional[int] = field(default_factory=lambda: None)
    # the max lifetime for this cluster (timedelta e.g. '2h', '2h30m')
    lifetime: Optional[str] = field(default_factory=lambda: None)
    # the max time for this cluster before getting removed when no client is connected
    session_timeout: Optional[str] = field(default_factory=lambda: None)
    # the max time waiting for this cluster to become 'READY'
    cluster_timeout: Optional[int] = field(
        default_factory=lambda: default_configuration.CLUSTER_CREATION_TIMEOUT
    )
    # the K8s resources (requests, limits) for the server and node pods
    server_resources: Optional[dict[str, dict[str, str]]] = field(
        default_factory=lambda: None
    )
    node_resources: Optional[dict[str, dict[str, str]]] = field(
        default_factory=lambda: None
    )
    # storage requests for server and node pods
    server_storage: Optional[str] = field(default_factory=lambda: None)
    node_storage: Optional[str] = field(default_factory=lambda: None)
    # Gefyra component requests
    gefyra: GefyraParams = field(default_factory=lambda: GefyraParams())

    @classmethod
    def from_raw(cls, data: dict):
        params = cls()
        params.ports = data.get("ports")
        params.nodes = data.get("nodes")
        params.lifetime = data.get("maxLifetime")
        params.session_timeout = data.get("maxSessionTimeout")
        params.cluster_timeout = data.get("clusterReadyTimeout")
        params.server_storage = data.get("serverStorageRequests")
        params.node_storage = data.get("nodeStorageRequests")
        return params

    def as_dict(self) -> dict[str, Any]:
        data = {}
        for _field in fields(self):
            if _v := getattr(self, _field.name):
                if type(_v) == GefyraParams:
                    data["gefyra"] = {
                        "enabled": _v.enabled,
                        "endpoint": _v.endpoint
                    }
                else:
                    data[_field.name] = _v
        return data


@dataclass
class BeibootRequest:
    # a unique name for this Beiboot cluster
    name: str
    # the K8s provider running the cluster
    provider: BeibootProvider = field(default_factory=lambda: BeibootProvider.K3S)
    parameters: BeibootParameters = field(default_factory=lambda: BeibootParameters())


class BeibootState(Enum):
    REQUESTED = "REQUESTED"
    CREATING = "CREATING"
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    READY = "READY"
    TERMINATING = "TERMINATING"
    ERROR = "ERROR"


class Beiboot:
    # the final name of this cluster
    name: str
    # the namespace this cluster runs in the host cluster
    namespace: str
    # the beiboot.getdeck.dev object name
    object_name: str
    # the beiboot.getdeck.dev object namespace
    object_namespace: str
    state: BeibootState
    transitions: Optional[dict[str, str]]
    parameters: BeibootParameters

    def __init__(
        self, beiboot: dict, config: ClientConfiguration = default_configuration
    ):
        self.name = beiboot["metadata"]["name"]
        self.object_name = beiboot["metadata"]["name"]
        self.namespace = beiboot.get("beibootNamespace")
        self.object_namespace = beiboot["metadata"]["namespace"]
        self._data = beiboot
        self._config = config
        self._init_data()

    def _init_data(self):
        self.state = self._data["state"]
        self.transitions = self._data["stateTransitions"]
        self.parameters = BeibootParameters.from_raw(self._data["parameters"])

    def _fetch_object(self):
        try:
            bbt = self._config.K8S_CUSTOM_OBJECT_API.get_namespaced_custom_object(
                group="getdeck.dev",
                version="v1",
                namespace=self._config.NAMESPACE,
                plural="beiboots",
                name=self.name,
            )
        except k8s.client.exceptions.ApiException as e:
            if e.status == 404:
                raise RuntimeError(
                    f"The Beiboot '{self.name}' does not exist anymore"
                ) from None
            else:
                raise RuntimeError(str(e)) from None
        self._init_data()
