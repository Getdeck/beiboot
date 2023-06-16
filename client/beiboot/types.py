import binascii
import logging
from datetime import datetime
from time import sleep

import kubernetes as k8s

from dataclasses import dataclass, field, fields
from enum import Enum
from typing import Dict, Optional, Any, Union, Type

from beiboot.configuration import (
    default_configuration,
    ClientConfiguration,
    __VERSION__,
)


logger = logging.getLogger(__name__)


class StateAndEventsMixin:
    # this mixin is used by Beiboot and Shelf
    # following class variables need to be set by class that uses this mixin
    StateClass: Optional[Union[Type["BeibootState"], Type["ShelfState"]]] = None
    # the uid from Kubernetes for this object
    uid: str
    _data: Optional[Dict[str, Any]] = None
    _config: ClientConfiguration  # check for shelf

    @property
    def state(self):
        self.fetch_object()
        return self.StateClass(self._data.get("state"))

    def fetch_object(self):
        raise NotImplementedError

    def wait_for_state(
        self, awaited_state: Union["BeibootState", "ShelfState"], timeout: int = 60
    ):
        """
        > Wait for the state of the resource to be the awaited state, or raise an error if the timeout is reached

        :param awaited_state: The state we're waiting for
        :type awaited_state: State enum class
        :param timeout: The maximum time to wait for the state to change, defaults to 60
        :type timeout: int (optional)
        :return: the state of the resource.
        """
        _i = 0
        while _i < timeout:
            if self.state == awaited_state:
                logger.info(
                    f"Done waiting for state {awaited_state.value} (is: {self.state.value}, {_i}s/{timeout}s) "
                )
                return
            else:
                logger.info(
                    f"Waiting for state {awaited_state.value} (is: {self.state.value}, {_i}s/{timeout}s) "
                )
                sleep(1)
                _i = _i + 1
        if self.state != awaited_state:
            raise RuntimeError(f"Waiting for state {awaited_state.value} failed")

    @property
    def events_by_timestamp(self) -> dict[datetime, Any]:
        """
        This function returns a dictionary of events related to this resource, sorted by timestamp
        :return: A dictionary of events sorted by timestamp.
        """
        try:
            events = self._config.K8S_CORE_API.list_namespaced_event(
                namespace=self._config.NAMESPACE
            )
            related_events = list(
                filter(lambda et: et.involved_object.uid == self.uid, events.items)
            )
        except k8s.client.ApiException as e:  # type: ignore
            raise RuntimeError(str(e)) from None
        result = {}
        for revent in related_events:
            result[revent.event_time] = {
                "reason": revent.reason,
                "reporter": revent.reporting_component,
                "message": revent.message,
            }
        return dict(sorted(result.items()))


class BeibootProvider(Enum):
    K3S = "k3s"


@dataclass
class GefyraParams:
    # deploy Gefyra components to this Beiboot
    enabled: bool = field(default_factory=lambda: True)
    # endpoint written to the kubeconfig for Gefyra
    endpoint: Optional[str] = field(default_factory=lambda: None)


@dataclass
class TunnelParams:
    # deploy Tunnel components to this Beiboot
    enabled: bool = field(default_factory=lambda: True)
    # endpoint for tunnel connection
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
    # Tunnel connection params
    tunnel: Optional[TunnelParams] = field(default_factory=lambda: TunnelParams())

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
        params.nodeResources = data.get("nodeResources")
        params.serverResources = data.get("serverResources")
        params.gefyra = data.get("gefyra")  # type: ignore
        params.tunnel = data.get("tunnel")  # type: ignore
        return params

    def as_dict(self) -> dict[str, Any]:
        data = {}
        for _field in fields(self):
            if _v := getattr(self, _field.name):
                if type(_v) == GefyraParams:
                    data["gefyra"] = {"enabled": _v.enabled, "endpoint": _v.endpoint}
                elif type(_v) == TunnelParams:
                    data["tunnel"] = {"enabled": _v.enabled, "endpoint": _v.endpoint}
                else:
                    data[_field.name] = _v
        if (data.get("tunnel") and data["tunnel"].get("endpoint")) and (
            data.get("gefyra") and data["gefyra"].get("endpoint") is None
        ):
            # if there is a special endpoint for tunnel and not for Gefyra, set it for Gefyra, too
            data["gefyra"]["endpoint"] = data["tunnel"].get("endpoint")
        return data


@dataclass
class BeibootRequest:
    # a unique name for this Beiboot cluster
    name: str
    # the K8s provider running the cluster
    provider: BeibootProvider = field(default_factory=lambda: BeibootProvider.K3S)
    parameters: BeibootParameters = field(default_factory=lambda: BeibootParameters())
    labels: Dict[str, str] = field(default_factory=lambda: {})
    from_shelf: str = field(default_factory=lambda: "")


class BeibootState(Enum):
    REQUESTED = "REQUESTED"
    PREPARING = "PREPARING"
    RESTORING = "RESTORING"
    CREATING = "CREATING"
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    READY = "READY"
    TERMINATING = "TERMINATING"
    ERROR = "ERROR"


class Beiboot(StateAndEventsMixin):
    # the final name of this cluster
    name: str
    # the namespace this cluster runs in the host cluster
    namespace: str
    # the beiboot.getdeck.dev object namespace
    object_namespace: str
    # the labels of this Beiboot object
    labels: Dict[str, str]
    # the timestamp when this cluster gets removed
    sunset: Optional[str] = None
    # the timestamp when any client reported its last heartbeat
    last_client_contact: Optional[str] = None
    # all state transitions
    transitions: Optional[dict[str, str]]
    # the cluster parameters
    parameters: BeibootParameters
    provider: str

    # class variables from StateMixin (_data is set in _init_data(...))
    StateClass = BeibootState

    def __init__(
        self, beiboot: dict, config: ClientConfiguration = default_configuration
    ):
        self.name = beiboot["metadata"]["name"]
        self.uid = beiboot["metadata"]["uid"]
        self.labels = beiboot["metadata"].get("labels")
        self.object_namespace = beiboot["metadata"]["namespace"]
        self.provider = beiboot["provider"]
        self._init_data(beiboot)
        self._config = config

    def _init_data(self, _object: dict[str, Any]):
        self._data = _object
        self.namespace = str(self._data.get("beibootNamespace"))
        self.sunset = self._data.get("sunset")
        self.last_client_contact = self._data.get("lastClientContact")
        self.transitions = self._data.get("stateTransitions")
        self.parameters = BeibootParameters.from_raw(self._data["parameters"])

    def fetch_object(self):
        logger.debug(f"Fetching object Beiboot {self.name}")
        try:
            bbt = self._config.K8S_CUSTOM_OBJECT_API.get_namespaced_custom_object(
                group="getdeck.dev",
                version="v1",
                namespace=self._config.NAMESPACE,
                plural="beiboots",
                name=self.name,
            )
        except k8s.client.exceptions.ApiException as e:  # type: ignore
            if e.status == 404:
                raise RuntimeError(
                    f"The Beiboot '{self.name}' does not exist anymore"
                ) from None
            else:
                raise RuntimeError(str(e)) from None
        self._init_data(bbt)  # type: ignore

    @property
    def kubeconfig(self) -> Optional[str]:
        """
        It returns the kubeconfig of the Beiboot.
        :return: The kubeconfig object is being returned.
        """
        from beiboot.utils import decode_kubeconfig

        if self.state != BeibootState.READY:
            logger.warning("This Beiboot is not in READY state")
        if self._data and "kubeconfig" in self._data:
            kubeconfig_object: Dict[str, str] = self._data["kubeconfig"]  # noqa
        else:
            return None
        try:
            kubeconfig = decode_kubeconfig(kubeconfig_object)
        except (KeyError, binascii.Error) as e:
            raise RuntimeError(f"Can not fetch kubeconfig: {e}") from None
        else:
            return kubeconfig

    @property
    def mtls_files(self) -> Optional[dict[str, str]]:
        """
        It returns the mTLS files for the Beiboot if it's in the READY state
        :return: The mtls_files property returns a dictionary of the mTLS files.
        """
        from beiboot.utils import decode_b64_dict

        if self.state != BeibootState.READY:
            logger.warning("This Beiboot is not in READY state")
        if tunnel := self.tunnel:
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
        """
        It returns a dictionary holding the service account token for the Beiboot
        :return: A dictionary holding the service account tokens.
        """
        from beiboot.utils import decode_b64_dict

        if self.state != BeibootState.READY:
            logger.warning("This Beiboot is not in READY state")
        if tunnel := self.tunnel:
            if sa_token := tunnel.get("serviceaccount"):
                try:
                    return decode_b64_dict(sa_token)
                except binascii.Error as e:
                    raise RuntimeError(
                        f"There was an error decoding the serviceaccount token: {e}"
                    ) from None
        return None

    @property
    def tunnel(self) -> Optional[dict[str, Any]]:
        if self._data and "tunnel" in self._data:
            return self._data["tunnel"]
        return None


@dataclass
class InstallOptions:
    namespace: str = field(
        default_factory=lambda: "getdeck",
        metadata=dict(
            help="The namespace to install Beiboot into (default: getdeck)", short="ns"
        ),
    )
    version: str = field(
        default_factory=lambda: __VERSION__,
        metadata=dict(
            help="Set the Operator version; components are created according to this beibootctl version"
        ),
    )
    storage_class: str = field(
        default_factory=lambda: "standard",
        metadata=dict(
            help="Set the Kubernetes StorageClass of PVCs created for Beiboot clusters (default: standard)"
        ),
    )
    shelf_storage_class: str = field(
        default_factory=lambda: "standard",
        metadata=dict(
            help="Set the Kubernetes VolumeSnapshotClass of VolumeSnapshots created for Beiboot shelf clusters (default: standard)"  # noqa: E501
        ),
    )
    node_storage_request: str = field(
        default_factory=lambda: "1Gi",
        metadata=dict(
            help="The default storage request for Beiboot nodes (default: 1Gi)"
        ),
    )
    server_storage_request: str = field(
        default_factory=lambda: "1Gi",
        metadata=dict(
            help="The default storage request for Beiboot servers (default: 1Gi)"
        ),
    )
    nodes: str = field(
        default_factory=lambda: "1",
        metadata=dict(help="The default nodes count per Beiboot (default: 1)"),
    )
    max_session_timeout: str = field(
        default_factory=lambda: "null",
        metadata=dict(
            help="The default maximum session timeout for a Beiboot cluster before it will be deleted (default: null)"
        ),
    )
    max_lifetime: str = field(
        default_factory=lambda: "null",
        metadata=dict(
            help="The default maximum lifetime for a Beiboot cluster before it will be deleted (default: null)"
        ),
    )
    namespace_prefix: str = field(
        default_factory=lambda: "getdeck-bbt",
        metadata=dict(
            help="The namespace prefix for Beiboot clusters within the host cluster (default: getdeck-bbt)",
        ),
    )
    server_requests_cpu: str = field(
        default_factory=lambda: "1",
        metadata=dict(
            help="The default CPU request for each Beiboot server pod (default: 1)",
        ),
    )
    server_requests_memory: str = field(
        default_factory=lambda: "1Gi",
        metadata=dict(
            help="The default memory request for each Beiboot server pod (default: 1Gi)",
        ),
    )
    node_requests_cpu: str = field(
        default_factory=lambda: "1",
        metadata=dict(
            help="The default CPU request for each Beiboot node pod (default: 1)",
        ),
    )
    node_requests_memory: str = field(
        default_factory=lambda: "1Gi",
        metadata=dict(
            help="The default memory request for each Beiboot node pod (default: 1Gi)",
        ),
    )


@dataclass
class VolumeSnapshotContentStatus(Enum):
    NOT_READY_TO_USE = "NOT_READY_TO_USE"
    READY_TO_USE = "READY_TO_USE"


@dataclass
class VolumeSnapshotContent:
    name: str
    snapshot_handle: str
    node: str
    status: VolumeSnapshotContentStatus = field(
        default_factory=lambda: VolumeSnapshotContentStatus.NOT_READY_TO_USE
    )


@dataclass
class ShelfRequest:
    # a unique name for this Shelf
    name: str
    cluster_name: str
    volume_snapshot_class: str = ""
    volume_snapshot_contents: list[VolumeSnapshotContent] = field(
        default_factory=lambda: []
    )
    labels: Dict[str, str] = field(default_factory=lambda: {})


class ShelfState(Enum):
    REQUESTED = "REQUESTED"
    CREATING = "CREATING"
    PREPARING = "PREPARING"
    PENDING = "PENDING"
    READY = "READY"
    TERMINATING = "TERMINATING"
    ERROR = "ERROR"


class Shelf(StateAndEventsMixin):
    # the final name of this cluster
    name: str
    # the namespace this shelf is located in the host cluster (currently it's always "getdeck")
    namespace: str
    # list of VolumeSnapshotContents that are contained in this shelf
    volume_snapshot_contents: Optional[list[VolumeSnapshotContent]]
    # the labels of this Beiboot object
    labels: Dict[str, str]
    # all state transitions
    transitions: Optional[dict[str, str]]

    # class variables from StateMixin (_data is set in _init_data(...))
    StateClass = ShelfState

    def __init__(
        self, shelf: dict, config: ClientConfiguration = default_configuration
    ):
        self.name = shelf["metadata"]["name"]
        self.uid = shelf["metadata"]["uid"]
        self.labels = shelf["metadata"].get("labels")
        self._init_data(shelf)
        self._config = config

    def _init_data(self, _object: dict[str, Any]):
        self._data = _object
        self.transitions = self._data.get("stateTransitions")
        self.volume_snapshot_contents = self._data.get("volumeSnapshotContents")

    def fetch_object(self):
        logger.debug(f"Fetching object Shelf {self.name}")
        try:
            shelf = self._config.K8S_CUSTOM_OBJECT_API.get_namespaced_custom_object(
                group="beiboots.getdeck.dev",
                version="v1",
                namespace=self._config.NAMESPACE,
                plural="shelves",
                name=self.name,
            )
        except k8s.client.exceptions.ApiException as e:  # type: ignore
            if e.status == 404:
                raise RuntimeError(
                    f"The Shelf '{self.name}' does not exist anymore"
                ) from None
            else:
                raise RuntimeError(str(e)) from None
        self._init_data(shelf)  # type: ignore
