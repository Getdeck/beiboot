import uuid
from datetime import datetime
from typing import Optional, Tuple

import kubernetes as k8s
import kopf

from beiboot.configuration import ShelfConfiguration
from beiboot.utils import StateMachine, AsyncState


class Shelf(StateMachine):
    """
    A Shelf is implemented as a state machine
    The body of the Shelf CRD is available as self.model
    """

    requested = AsyncState("Shelf requested", initial=True, value="REQUESTED")
    creating = AsyncState("Shelf creating", value="CREATING")
    pending = AsyncState("Shelf pending", value="PENDING")
    # TODO: do we need partially_ready, or are we fine with creating/pending
    ready = AsyncState("Shelf ready", value="READY")
    error = AsyncState("Shelf error", value="ERROR")
    terminating = AsyncState("Shelf terminating", value="TERMINATING")

    create = requested.to(creating) | error.to(creating)
    shelve = creating.to(pending)
    reconcile = pending.to(ready) | ready.to.itself() | error.to(ready)
    impair = error.from_(ready, pending, creating, requested, error)
    terminate = terminating.from_(pending, creating, ready, error, terminating)

    def __init__(
        self,
        configuration: ShelfConfiguration,
        model=None,
        logger=None,
        persistent_volume_claims: dict = None,
    ):
        super(Shelf, self).__init__()
        self.configuration = configuration
        self.model = model
        self.current_state_value = model.get("state")
        self.logger = logger
        self.persistent_volume_claims = persistent_volume_claims
        self.custom_api = k8s.client.CustomObjectsApi()
        self.core_api = k8s.client.CoreV1Api()
        self.events_api = k8s.client.EventsV1Api()

    def set_persistent_volume_claims(self, persistent_volume_claims: dict):
        self.persistent_volume_claims = persistent_volume_claims

    @property
    def name(self) -> str:
        """
        It returns the name of the cluster
        :return: The name of the cluster.
        """
        # TODO: refactor with clusterstate
        return self.model["metadata"]["name"]

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
        It creates the VolumeSnapshots
        """
        # - find out provider
        # - get parameters to store on CRD
        # - get list of PVCs to shelve from provider
        # - create VolumeSnapshot for each PVC
        # - find out associated VolumeSnapshotContent and store on CRD
        self.logger.debug(f"pvc_mapping: {self.persistent_volume_claims}")
        volume_snapshot_contents = []
        for sts_name, pvc_name in self.persistent_volume_claims.items():
            volume_snapshot_contents.append({
                "node": sts_name,
                "pvc": pvc_name,
            })
        data = {
            "volumeSnapshotContents": volume_snapshot_contents
        }
        self._patch_object(data)

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
