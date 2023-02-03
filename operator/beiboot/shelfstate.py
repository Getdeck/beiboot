import uuid
from datetime import datetime
from typing import Optional, Tuple

import kubernetes as k8s
import kopf

from beiboot.clusterstate import BeibootCluster
from beiboot.configuration import ShelfConfiguration, ClusterConfiguration
from beiboot.resources.utils import create_volume_snapshot_from_pvc_resource, handle_create_volume_snapshot, \
    handle_delete_volume_snapshot, handle_delete_volume_snapshot_content
from beiboot.utils import StateMachine, AsyncState

objects_api = k8s.client.CustomObjectsApi()


class Shelf(StateMachine):
    """
    A Shelf is implemented as a state machine
    The body of the Shelf CRD is available as self.model
    """

    requested = AsyncState("Shelf requested", initial=True, value="REQUESTED")
    creating = AsyncState("Shelf creating", value="CREATING")
    preparing = AsyncState("Shelf preparing (cluster-specific stuff)", value="PREPARING")
    pending = AsyncState("Shelf pending", value="PENDING")
    ready = AsyncState("Shelf ready", value="READY")
    error = AsyncState("Shelf error", value="ERROR")
    terminating = AsyncState("Shelf terminating", value="TERMINATING")

    create = requested.to(creating) | error.to(creating)
    pre_shelve = creating.to(preparing)
    shelve = preparing.to(pending)
    operate = pending.to(ready)
    reconcile = ready.to.itself() | error.to(ready)
    impair = error.from_(ready, pending, preparing, creating, requested, error)
    terminate = terminating.from_(pending, preparing, creating, ready, error, terminating)

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
        self._volume_snapshot_names = []
        self.cluster_default_volume_snapshot_class = cluster_default_volume_snapshot_class
        self._cluster_namespace = cluster_namespace
        self.cluster_parameters = None
        self.custom_api = k8s.client.CustomObjectsApi()
        self.core_api = k8s.client.CoreV1Api()
        self.events_api = k8s.client.EventsV1Api()

    def set_persistent_volume_claims(self, persistent_volume_claims: dict):
        self.persistent_volume_claims = persistent_volume_claims

    def set_cluster_namespace(self, namespace: str):
        self._cluster_namespace = namespace

    def set_cluster_parameters(self, cluster_parameters: ClusterConfiguration):
        self.cluster_parameters = cluster_parameters

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
            volume_snapshot_names = [f"{self.name}-{node_name}" for node_name in pvc_mapping.keys()]
        else:
            pvc_mapping = {}
            volume_snapshot_names = []
            for volume_snapshot_content in self.model["volumeSnapshotContents"]:
                pvc_name = volume_snapshot_content.get("pvc")
                node_name = volume_snapshot_content.get("node")
                pvc_mapping[node_name] = pvc_name
                volume_snapshot_names.append(f"{self.name}-{node_name}")
        # we need this as self.model is not updated immediately
        self._volume_snapshot_names = volume_snapshot_names
        return pvc_mapping

    @property
    def volume_snapshot_class(self):
        return self.model["volumeSnapshotClass"] or self.cluster_default_volume_snapshot_class

    @property
    def cluster_namespace(self):
        return self.model["clusterNamespace"] or self._cluster_namespace

    @property
    def volume_snapshot_names(self):
        if self._volume_snapshot_names:
            return self._volume_snapshot_names
        else:
            names = []
            for volume_snapshot_content in self.model["volumeSnapshotContents"]:
                try:
                    names.append(volume_snapshot_content["volumeSnapshotName"])
                except KeyError:
                    continue
            return names

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
        > The function posts an event to the Kubernetes API, and then patches the custom resource with the parameters
        """
        import dataclasses

        self.post_event(
            self.creating.value, f"The shelf '{self.name}' is now being created"
        )

        self._patch_object({
                "clusterParameters": dataclasses.asdict(self.cluster_parameters),
            })

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
                "volumeSnapshotName": f"{self.name}-{sts_name}",
            })
        data = {
            "clusterNamespace": self.cluster_namespace,
            "volumeSnapshotClass": self.volume_snapshot_class,
            "volumeSnapshotContents": volume_snapshot_contents,
        }

        self._patch_object(data)

    async def on_pre_shelve(self, cluster: BeibootCluster):
        """
        Call cluster providers hook before shelf is actually created
        """
        self.logger.info("on_pre_shelve")
        await cluster.provider.on_shelf_request()

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
            handle_create_volume_snapshot(self.logger, body=volume_snapshot_resource)
        self.post_event(
            self.creating.value, f"Now waiting for the shelf '{self.name}' to enter ready state"
        )

    async def on_operate(self):
        """If shelf is ready (i.e. VolumeSnapshots and VolumeSnapshotContents have readyToUse=True), post the event
        and return. If the shelf is pending, check if it's been pending for longer than the timeout."""
        if await self._volume_snapshots_ready():
            self.logger.info(f"VolumeSnapshotContents are ready")
            self.post_event(
                self.requested.value,
                f"The shelf is ready to use (i.e. all VolumeSnapshotContents for '{self.name}' are readyToUse)"
            )
        else:
            # TODO: add timeout logic
            raise kopf.TemporaryError(
                f"Waiting for shelf '{self.name}' to enter ready state (i.e. for all VolumeSnapshots to be readyToUse)",
                delay=5,
            )

    async def on_enter_terminating(self):
        """
        Try to delete VolumeSnapshots, delete VolumeSnapshotContents
        """
        try:
            await self._delete()
        except k8s.client.ApiException:
            pass

    async def on_impair(self, reason: str):
        self.post_event(self.error.value, f"The shelf has become defective: {reason}")

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

    async def _volume_snapshots_ready(self):
        """
        Check whether VolumeSnapshots/VolumeSnapshotContents are readyToUse and update shelf CRD data if necessary.
        """
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
        # store a list of booleans to represent readyToUse of every VolumeSnapshotContent
        ready = []

        if not self.model["volumeSnapshotContents"]:
            raise kopf.TemporaryError(
                f"No volumeSnapshotContents on shelf CRD '{self.name}'",
                delay=1
            )
        # we iterate over the data in the CRD, as we trust that it holds the desired target state (regarding number of
        # snapshots)
        # it might be that VolumeSnapshots/VolumeSnapshotContents are for some reason not there (e.g. they
        # were deleted manually), so we don't iterate over them
        for crd_data in self.model["volumeSnapshotContents"]:
            volume_snapshot_name = crd_data["volumeSnapshotName"]
            if volume_snapshot_name in self.volume_snapshot_names:
                volume_snapshot = self._get_volume_snapshot_from_list(volume_snapshots["items"], volume_snapshot_name)
                if not volume_snapshot and not crd_data["name"]:
                    # We neither have the VolumeSnapshot nor the VolumeSnapshotContent. It might be, that both have not
                    # yet been created in K8s. If e.g. the beiboot cluster was deleted and with it the VolumeSnapshot,
                    # we need to have the name of the VolumeSnapshotContent stored in the shelf CRD
                    data_volume_snapshot_contents.append(crd_data)
                    ready.append(False)
                    continue

                volume_snapshot_content_name = crd_data["name"] or \
                                               volume_snapshot.get("status", {}).get("boundVolumeSnapshotContentName")
                volume_snapshot_content = self._get_volume_snapshot_content_from_list(
                    volume_snapshot_contents["items"],
                    volume_snapshot_content_name
                )
                if not volume_snapshot_content:
                    data_volume_snapshot_contents.append(crd_data)
                    ready.append(False)
                    continue

                if volume_snapshot_content.get("status", {}).get("readyToUse"):
                    ready.append(True)
                else:
                    ready.append(False)

                data = crd_data.copy()
                data["snapshotHandle"] = volume_snapshot_content.get("status", {}).get("snapshotHandle", "")
                data["name"] = volume_snapshot_content_name
                data_volume_snapshot_contents.append(data)

        if data_volume_snapshot_contents != self.model["volumeSnapshotContents"]:
            data = {
                "volumeSnapshotContents": data_volume_snapshot_contents
            }
            self._patch_object(data)

        return all(ready)

    def _get_volume_snapshot_from_list(self, iterable: list, name: str):
        """Return VolumeSnapshot from list that was returned bei k8s api."""
        if name:
            for element in iterable:
                if element["metadata"]["name"] == name:
                    return element
        return None

    def _get_volume_snapshot_content_from_list(self, iterable: list, name: str):
        """Return VolumeSnapshotContent from list that was returned bei k8s api."""
        if name:
            for element in iterable:
                if element["metadata"]["name"] == name:
                    return element
        return None

    def _get_crd_volume_snapshot_content_from_list(self, iterable: list, name: str):
        """Return volumeSnapshotContent from list that is stored in shelf crd."""
        for element in iterable:
            if element.get("volumeSnapshotName") == name:
                return element
        return None

    async def _delete(self):
        for crd_data in self.model["volumeSnapshotContents"]:
            node_name = crd_data.get("node")
            volume_snapshot_name = f"{self.name}-{node_name}"
            await handle_delete_volume_snapshot(
                logger=self.logger,
                name=volume_snapshot_name,
                namespace=self.cluster_namespace
            )
            volume_snapshot_content_name = crd_data.get("name")
            await handle_delete_volume_snapshot_content(
                logger=self.logger,
                name=volume_snapshot_content_name,
            )
