import uuid
from datetime import datetime
from typing import Optional, Tuple

import kubernetes as k8s
import kopf

from beiboot.configuration import ShelfConfiguration
from beiboot.resources.utils import create_volume_snapshot_from_pvc_resource, handle_create_volume_snapshot
from beiboot.utils import StateMachine, AsyncState

objects_api = k8s.client.CustomObjectsApi()


class Shelf(StateMachine):
    """
    A Shelf is implemented as a state machine
    The body of the Shelf CRD is available as self.model
    """

    requested = AsyncState("Shelf requested", initial=True, value="REQUESTED")
    creating = AsyncState("Shelf creating", value="CREATING")
    pending = AsyncState("Shelf pending", value="PENDING")
    ready = AsyncState("Shelf ready", value="READY")
    error = AsyncState("Shelf error", value="ERROR")
    terminating = AsyncState("Shelf terminating", value="TERMINATING")

    create = requested.to(creating) | error.to(creating)
    shelve = creating.to(pending)
    operate = pending.to(ready)
    reconcile = ready.to.itself() | error.to(ready)
    impair = error.from_(ready, pending, creating, requested, error)
    terminate = terminating.from_(pending, creating, ready, error, terminating)

    def __init__(
        self,
        configuration: ShelfConfiguration,
        model=None,
        logger=None,
        persistent_volume_claims: dict = None,
        cluster_default_volume_snapshot_class: str = None,
        cluster_namespace: str = None,
    ):
        super(Shelf, self).__init__()
        self.configuration = configuration
        self.model = model
        self.current_state_value = model.get("state")
        self.logger = logger
        self.persistent_volume_claims = persistent_volume_claims
        self.volume_snapshot_names = []
        self.cluster_default_volume_snapshot_class = cluster_default_volume_snapshot_class
        self._cluster_namespace = cluster_namespace
        self.custom_api = k8s.client.CustomObjectsApi()
        self.core_api = k8s.client.CoreV1Api()
        self.events_api = k8s.client.EventsV1Api()

    def set_persistent_volume_claims(self, persistent_volume_claims: dict):
        self.persistent_volume_claims = persistent_volume_claims

    def set_cluster_namespace(self, namespace: str):
        self._cluster_namespace = namespace

    def set_cluster_default_volume_snapshot_class(self, volume_snapshot_class: str):
        self.cluster_default_volume_snapshot_class = volume_snapshot_class

    @property
    def name(self) -> str:
        """
        It returns the name of the cluster
        :return: The name of the cluster.
        """
        # TODO: refactor with clusterstate
        return self.model["metadata"]["name"]

    @property
    def pvc_mapping(self) -> dict:
        """
        Return mapping of node-name to PVC that node uses and set internal list of VolumeSnapshot-names
        """
        if self.persistent_volume_claims:
            pvc_mapping = self.persistent_volume_claims
            volume_snapshot_names = [f"{self.name}-{pvc_name}" for pvc_name in pvc_mapping.keys()]
        else:
            pvc_mapping = {}
            volume_snapshot_names = []
            for volume_snapshot_content in self.model["volumeSnapshotContents"]:
                pvc_name = volume_snapshot_content.get("pvc")
                pvc_mapping[volume_snapshot_content.get("node")] = pvc_name
                volume_snapshot_names.append(f"{self.name}-{pvc_name}")
        # TODO: this only works if all states are traversed!
        self.volume_snapshot_names = volume_snapshot_names
        return pvc_mapping

    @property
    def volume_snapshot_class(self):
        return self.model["volumeSnapshotClass"] or self.cluster_default_volume_snapshot_class

    @property
    def cluster_namespace(self):
        return self.model["clusterNamespace"] or self._cluster_namespace

    def completed_transition(self, state_value: str) -> Optional[str]:
        """
        Read the stateTransitions attribute, return the value of the stateTransitions timestamp for the given
        state_value, otherwise return None

        :param state_value: The value of the state value
        :type state_value: str
        :return: The value of the stateTransitions key in the model dictionary.
        """
        # TODO: refactor with clusterstate
        if transitions := self.model.get("stateTransitions"):
            return transitions.get(state_value, None)
        else:
            return None

    def get_latest_transition(self) -> Optional[datetime]:
        """
        > Get the latest transition time for a cluster
        :return: The latest transition times
        """
        # TODO: refactor with clusterstate
        timestamps = list(
            filter(
                lambda k: k is not None,
                [
                    self.completed_transition(Shelf.ready.value),
                    self.completed_transition(Shelf.error.value),
                ],
            )
        )
        if timestamps:
            return max(
                map(
                    lambda x: datetime.fromisoformat(x.strip("Z")),  # type: ignore
                    timestamps,
                )
            )
        else:
            return None

    def get_latest_state(self) -> Optional[Tuple[str, datetime]]:
        """
        It returns the latest state of the cluster, and the timestamp of when it was in that state
        :return: A tuple of the latest state and the timestamp of the latest state.
        """
        # TODO: refactor with clusterstate
        states = list(
            filter(
                lambda k: k[1] is not None,
                {
                    Shelf.creating.value: self.completed_transition(
                        Shelf.creating.value
                    ),
                    Shelf.pending.value: self.completed_transition(
                        Shelf.pending.value
                    ),
                    Shelf.ready.value: self.completed_transition(
                        Shelf.ready.value
                    ),
                    Shelf.error.value: self.completed_transition(
                        Shelf.error.value
                    ),
                }.items(),
            )
        )
        if states:
            latest_state, latest_timestamp = None, None
            for state, timestamp in states:
                if latest_state is None:
                    latest_state = state
                    latest_timestamp = datetime.fromisoformat(timestamp.strip("Z"))  # type: ignore
                else:
                    _timestamp = datetime.fromisoformat(timestamp.strip("Z"))
                    if latest_timestamp < _timestamp:
                        latest_state = state
                        latest_timestamp = _timestamp
            return latest_state, latest_timestamp  # type: ignore
        else:
            return None

    def on_enter_state(self, destination, *args, **kwargs):
        """
        If the current state value is not the same as the latest state value, write the current state value to the
        Shelf object

        :param destination: The state that the machine is transitioning to
        """
        # TODO: refactor with clusterstate
        if self.get_latest_state():
            state, _ = self.get_latest_state()
            if self.current_state_value != state:
                self._write_state()
        else:
            self._write_state()

    def on_enter_requested(self) -> None:
        """
        > The function `on_enter_requested` is called when the state machine enters the `requested` state
        """
        # post CRD object create hook
        self.post_event(
            self.requested.value,
            f"The shelf request for '{self.name}' has been accepted",
        )

    def on_create(self):
        """
        > The function posts an event to the Kubernetes API
        """
        self.post_event(
            self.creating.value, f"The shelf '{self.name}' is now being created"
        )

    async def on_enter_creating(self):
        """
        Set necessary fields in shelf CRD if needed.

        - store the node- and PVC-names on the shelf CRD
        - set volumeSnapshotClass if not set
        """
        volume_snapshot_contents = []
        for sts_name, pvc_name in self.persistent_volume_claims.items():
            volume_snapshot_contents.append({
                "node": sts_name,
                "pvc": pvc_name,
            })
        data = {
            "clusterNamespace": self.cluster_namespace,
            "volumeSnapshotContents": volume_snapshot_contents,
            "volumeSnapshotClass": self.volume_snapshot_class
        }

        self._patch_object(data)

    async def on_shelve(self):
        """
        Create VolumeSnapshots
        """
        for node_name, pvc_name in self.pvc_mapping.items():
            volume_snapshot_resource = create_volume_snapshot_from_pvc_resource(
                name=f"{self.name}-{node_name}",
                namespace=self.cluster_namespace,
                volume_snapshot_class=self.volume_snapshot_class,
                pvc_name=pvc_name
            )
            self.logger.info(f"volume_snapshot_resource: {volume_snapshot_resource}")
            handle_create_volume_snapshot(self.logger, body=volume_snapshot_resource)

    async def on_operate(self):
        """If shelf is ready (i.e. VolumeSnapshots and VolumeSnapshotContents have readyToUse=True), post the event
        and return. If the shelf is pending, check if it's been pending for longer than the timeout."""
        if await self.volume_snapshots_ready():
            self.logger.info(f"snapshots are ready")
            # TODO: add event posting
        else:
            # TODO: add timeout logic
            raise kopf.TemporaryError(
                f"Waiting for shelf '{self.name}' to enter ready state (i.e. for all VolumeSnapshots to be readyToUse",
                delay=1,
            )

    def _get_now(self) -> str:
        # TODO: refactor with clusterstate
        return datetime.utcnow().isoformat(timespec="microseconds") + "Z"

    def post_event(self, reason: str, message: str, _type: str = "Normal") -> None:
        """
        It creates an event object and posts it to the Kubernetes API

        :param reason: The reason for the event
        :type reason: str
        :param message: The message to be displayed in the event
        :type message: str
        :param _type: The type of event, defaults to Normal
        :type _type: str (optional)
        """
        # TODO: refactor with clusterstate
        now = self._get_now()
        event = k8s.client.EventsV1Event(
            metadata=k8s.client.V1ObjectMeta(
                name=f"{self.name}-{uuid.uuid4()}",
                namespace=self.configuration.NAMESPACE,
            ),
            reason=reason.capitalize(),
            note=message[:1024],  # maximum message length
            event_time=now,
            action="Shelf-State",
            type=_type,
            reporting_instance="beiboot-operator",
            reporting_controller="beiboot-operator",
            regarding=k8s.client.V1ObjectReference(
                kind="shelf",
                name=self.name,
                namespace=self.configuration.NAMESPACE,
                uid=self.model.metadata["uid"],
            ),
        )
        self.events_api.create_namespaced_event(
            namespace=self.configuration.NAMESPACE, body=event
        )

    def _write_state(self):
        # TODO: refactor with clusterstate
        data = {
            "state": self.current_state.value,
            "stateTransitions": {self.current_state.value: self._get_now()},
        }
        self._patch_object(data)

    def _patch_object(self, data: dict):
        # TODO: refactor with clusterstate
        self.custom_api.patch_namespaced_custom_object(
            namespace=self.configuration.NAMESPACE,
            name=self.name,
            body=data,
            group="beiboots.getdeck.dev",
            plural="shelves",
            version="v1",
        )

    async def volume_snapshots_ready(self):
        volume_snapshots = objects_api.list_namespaced_custom_object(
            group="snapshot.storage.k8s.io",
            version="v1",
            namespace=self.cluster_namespace,
            plural="volumesnapshots",
        )
        volume_snapshot_contents = objects_api.list_cluster_custom_object(
            group="snapshot.storage.k8s.io",
            version="v1",
            plural="volumesnapshotcontents",
        )
        if not volume_snapshot_contents["items"]:
            raise kopf.TemporaryError(
                f"No VolumeSnapshotContents available.",
                delay=1,
            )
        # store data that we might want to update on the CRD
        data_volume_snapshot_contents = []
        all_ready = True
        self.logger.info(f"type(volume_snapshots): {type(volume_snapshots)}")
        self.logger.info(f"volume_snapshots: {volume_snapshots}")
        for volume_snapshot in volume_snapshots["items"]:
            self.logger.info(f"volume_snapshot: {volume_snapshot}")
            volume_snapshot_name = volume_snapshot["metadata"]["name"]
            if volume_snapshot_name in self.volume_snapshot_names:
                if not volume_snapshot["status"].get("readyToUse"):
                    all_ready = False
                crd_data = self._get_crd_volume_snapshot_content_from_list(
                    self.model["volumeSnapshotContents"],
                    volume_snapshot_name
                )
                volume_snapshot_content_name = volume_snapshot["status"].get("boundVolumeSnapshotContentName")
                volume_snapshot_content = self._get_volume_snapshot_content_from_list(
                    volume_snapshot_contents["items"],
                    volume_snapshot_content_name
                )
                if not crd_data or not volume_snapshot_content:
                    self.logger.info(
                        f"CRD volumeSnapshotContent: {crd_data} | K8s VolumeSnapshotContent: {volume_snapshot_content}"
                    )
                    raise kopf.TemporaryError(
                        f"volume_snapshot_content not found in shelf CRD, or in VolumeSnapshotContents, for "
                        f"VolumeSnapshot {volume_snapshot_name}",
                        delay=1,
                    )
                data_volume_snapshot_contents.append({
                    "snapshotHandle": volume_snapshot_content["status"].get("snapshotHandle", ""),
                    "node": crd_data["node"],
                    "pvc": crd_data["pvc"],
                    "name": volume_snapshot_content_name,
                })

        if data_volume_snapshot_contents != self.model["volumeSnapshotContents"]:
            data = {
                "volumeSnapshotContent": data_volume_snapshot_contents
            }
            self._patch_object(data)
        return all_ready

    def _get_volume_snapshot_content_from_list(self, iterable: list, name: str):
        """Return VolumeSnapshotContent from list that was returned bei k8s api."""
        for element in iterable:
            if element["metadata"]["name"] == name:
                return element
        return None

    def _get_crd_volume_snapshot_content_from_list(self, iterable: list, name: str):
        """Return volumeSnapshotContent from list that is stored in shelf crd."""
        for element in iterable:
            if element["name"] == name:
                return element
        return None

    def set_volume_snapshot_contents(self):
        pass
