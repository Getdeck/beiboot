import binascii
import logging
from datetime import datetime
from time import sleep

import kubernetes as k8s

from dataclasses import dataclass, field, fields
from enum import Enum
from typing import Optional, Any, Union

from beiboot.configuration import default_configuration, ClientConfiguration


logger = logging.getLogger(__name__)


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
    k8sVersion: Optional[str] = field(default_factory=lambda: None)
    # the ports mapped to local host
    ports: Optional[list[str]] = field(default_factory=lambda: None)
    # amount of nodes for this cluster
    nodes: Optional[int] = field(default_factory=lambda: None)
    # the max lifetime for this cluster (timedelta e.g. '2h', '2h30m')
    maxLifetime: Optional[str] = field(default_factory=lambda: None)
    # the max time for this cluster before getting removed when no client is connected
    maxSessionTimeout: Optional[str] = field(default_factory=lambda: None)
    # the max time waiting for this cluster to become 'READY'
    clusterReadyTimeout: Optional[int] = field(
        default_factory=lambda: default_configuration.CLUSTER_CREATION_TIMEOUT
    )
    # the K8s resources (requests, limits) for the server and node pods
    serverResources: Optional[dict[str, dict[str, str]]] = field(
        default_factory=lambda: None
    )
    nodeResources: Optional[dict[str, dict[str, str]]] = field(
        default_factory=lambda: None
    )
    # storage requests for server and node pods
    serverStorageRequests: Optional[str] = field(default_factory=lambda: None)
    nodeStorageRequests: Optional[str] = field(default_factory=lambda: None)
    # Gefyra component requests
    gefyra: GefyraParams = field(default_factory=lambda: GefyraParams())

    @classmethod
    def from_raw(cls, data: dict):
        params = cls()
        params.ports = data.get("ports")
        params.nodes = data.get("nodes")
        params.maxLifetime = data.get("maxLifetime")
        params.maxSessionTimeout = data.get("maxSessionTimeout")
        params.clusterReadyTimeout = data.get("clusterReadyTimeout")
        params.serverStorageRequests = data.get("serverStorageRequests")
        params.nodeStorageRequests = data.get("nodeStorageRequests")
        params.gefyra = data.get("gefyra")  # type: ignore
        return params

    def as_dict(self) -> dict[str, Any]:
        data = {}
        for _field in fields(self):
            if _v := getattr(self, _field.name):
                if type(_v) == GefyraParams:
                    data["gefyra"] = {"enabled": _v.enabled, "endpoint": _v.endpoint}
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
    # the uid from Kubernetes for this object
    uid: str
    # the beiboot.getdeck.dev object namespace
    object_namespace: str
    sunset: Optional[str] = None
    transitions: Optional[dict[str, str]]
    parameters: BeibootParameters

    def __init__(
        self, beiboot: dict, config: ClientConfiguration = default_configuration
    ):
        self.name = beiboot["metadata"]["name"]
        self.uid = beiboot["metadata"]["uid"]
        self.object_namespace = beiboot["metadata"]["namespace"]
        self._init_data(beiboot)
        self._config = config

    def _init_data(self, _object: dict[str, Any]):
        self._data = _object
        self.namespace = str(self._data.get("beibootNamespace"))
        self.sunset = self._data.get("sunset")
        self.transitions = self._data.get("stateTransitions")
        self.parameters = BeibootParameters.from_raw(self._data["parameters"])

    @property
    def state(self):
        self.fetch_object()
        return BeibootState(self._data.get("state"))

    def fetch_object(self):
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
        self._init_data(bbt)

    @property
    def kubeconfig(self) -> Optional[str]:
        from beiboot.utils import decode_kubeconfig

        if self.state != BeibootState.READY:
            logger.warning("This Beiboot is not in READY state")
        kubeconfig_object = self._data.get("kubeconfig")  # noqa
        if kubeconfig_object is None:
            return None
        try:
            kubeconfig = decode_kubeconfig(kubeconfig_object)
        except (KeyError, binascii.Error) as e:
            raise RuntimeError(f"Can not fetch kubeconfig: {e}") from None
        else:
            return kubeconfig

    @property
    def mtls_files(self) -> Optional[dict[str, str]]:
        from beiboot.utils import decode_b64_dict

        if self.state != BeibootState.READY:
            logger.warning("This Beiboot is not in READY state")
        if tunnel := self._data.get("tunnel"):
            if ghostunnel := tunnel.get("ghostunnel"):
                try:
                    return decode_b64_dict(ghostunnel["mtls"])
                except binascii.Error as e:
                    raise RuntimeError(
                        f"There was an error decoding mTLS data: {e}"
                    ) from None
        return None

    @property
    def serviceaccount_tokens(self) -> Optional[dict[str, Union[str, Any]]]:
        from beiboot.utils import decode_b64_dict

        if self.state != BeibootState.READY:
            logger.warning("This Beiboot is not in READY state")
        if tunnel := self._data.get("tunnel"):
            if sa_token := tunnel.get("serviceaccount"):
                try:
                    return decode_b64_dict(sa_token)
                except binascii.Error as e:
                    raise RuntimeError(
                        f"There was an error decoding the serviceaccount token: {e}"
                    ) from None
        return None

    @property
    def events_by_timestamp(self) -> dict[datetime, Any]:
        try:
            events = self._config.K8S_CORE_API.list_namespaced_event(
                namespace=self._config.NAMESPACE
            )
            related_events = list(
                filter(lambda et: et.involved_object.uid == self.uid, events.items)
            )
        except k8s.client.ApiException as e:
            raise RuntimeError(str(e)) from None
        result = {}
        for revent in related_events:
            result[revent.event_time] = {
                "reason": revent.reason,
                "reporter": revent.reporting_component,
                "message": revent.message,
            }
        return dict(sorted(result.items()))

    def wait_for_state(self, awaited_state: BeibootState, timeout: int = 60):
        _i = 0
        while _i < timeout:
            if self.state == awaited_state:
                return
            else:
                logger.info(f"Waiting for state {awaited_state.value} (is: {self.state.value}, {_i}s/{timeout}s) ")
                sleep(1)
                _i = _i + 1
        if self.state != awaited_state:
            raise RuntimeError(f"Waiting for state {awaited_state.value} failed")
