import base64
import json
import uuid
from asyncio import sleep
from datetime import datetime, timedelta
from json import JSONDecodeError
from typing import Optional

import kubernetes as k8s
import kopf

from beiboot.comps.ghostunnel import handle_ghostunnel_components
from beiboot.configuration import BeibootConfiguration, ClusterConfiguration
from beiboot.provider.abstract import AbstractClusterProvider
from beiboot.provider.factory import cluster_factory, ProviderType
from beiboot.resources.services import ports_to_services
from beiboot.resources.utils import (
    handle_create_namespace,
    handle_create_service,
    handle_delete_namespace,
    handle_create_beiboot_serviceaccount,
)
from beiboot.utils import StateMachine, AsyncState


class BeibootCluster(StateMachine):
    """
    A Beiboot cluster is implemented as a state machine
    The body of the Beiboot CRD is available as self.model
    """

    requested = AsyncState("Cluster requested", initial=True, value="REQUESTED")
    creating = AsyncState("Cluster creating", value="CREATING")
    pending = AsyncState("Cluster pending", value="PENDING")
    running = AsyncState("Cluster running", value="RUNNING")
    ready = AsyncState("Cluster ready", value="READY")
    error = AsyncState("Cluster error", value="ERROR")
    terminating = AsyncState("Cluster terminating", value="TERMINATING")

    create = requested.to(creating) | error.to(creating)
    boot = creating.to(pending)
    operate = pending.to(running)
    reconcile = running.to(ready) | ready.to.itself() | error.to(ready)
    recover = error.to(running)
    impair = error.from_(ready, running, pending, creating, requested, error)
    terminate = terminating.from_(pending, creating, running, ready, error, terminating)

    def __init__(
        self,
        configuration: BeibootConfiguration,
        parameters: ClusterConfiguration,
        model=None,
        logger=None,
    ):
        super(BeibootCluster, self).__init__()
        self.model = model
        self.current_state_value = model.get("state")
        self.logger = logger
        self.configuration = configuration
        self.parameters = parameters
        self.custom_api = k8s.client.CustomObjectsApi()
        self.core_api = k8s.client.CoreV1Api()
        self.events_api = k8s.client.EventsV1Api()

    @property
    def name(self) -> str:
        """
        It returns the name of the cluster
        :return: The name of the cluster.
        """
        return self.model["metadata"]["name"]

    @property
    def namespace(self) -> str:
        """
        If the namespace was already persisted to the CRD object, take it from there, otherwise, generate the name
        :return: The namespace name.
        """
        # if the namespace was already persisted to the CRD object, take it from there
        if namespace := self.model.get("beibootNamespace"):
            return namespace
        else:
            # otherwise, generate the name
            from beiboot.utils import get_namespace_name

            return get_namespace_name(self.name, self.parameters)

    @property
    def provider(self) -> AbstractClusterProvider:
        """
        It creates a cluster provider object based on the provider type
        :return: The provider is being returned.
        """
        provider = cluster_factory.get(
            ProviderType(self.model.get("provider")),
            self.configuration,
            self.parameters,
            self.name,
            self.namespace,
            self.model.get("ports"),
            self.logger,
        )
        if provider is None:
            raise kopf.PermanentError(
                f"Cannot create Beiboot with provider {self.model.get('provider')}: not supported."
            )
        return provider

    @property
    async def kubeconfig(self) -> Optional[str]:
        """
        If the CRD already has a kubeconfig, use it, otherwise extract the provider's kubeconfig from the cluster
        :return: The kubeconfig is being returned.
        """
        if source := self.model.get("kubeconfig"):
            if enc_kubeconfig := source.get("source"):
                kubeconfig = base64.b64decode(enc_kubeconfig).decode("utf-8")
            else:
                kubeconfig = await self.provider.get_kubeconfig()
        else:
            kubeconfig = await self.provider.get_kubeconfig()
        return kubeconfig

    def completed_transition(self, state_value: str) -> Optional[str]:
        """
        Read the stateTransitions attribute, return the value of the stateTransitions timestamp for the given
        state_value, otherwise return None

        :param state_value: The value of the state value
        :type state_value: str
        :return: The value of the stateTransitions key in the model dictionary.
        """
        if transitions := self.model.get("stateTransitions"):
            return transitions.get(state_value, None)
        else:
            return None

    def get_latest_transition(self) -> Optional[datetime]:
        """
        > Get the latest transition time for a cluster
        :return: The latest transition times
        """
        timestamps = list(
            filter(
                lambda k: k is not None,
                [
                    self.completed_transition(BeibootCluster.running.value),
                    self.completed_transition(BeibootCluster.ready.value),
                    self.completed_transition(BeibootCluster.error.value),
                ],
            )
        )
        if timestamps:
            return max(
                map(
                    lambda x: datetime.fromisoformat(x.strip("Z")),
                    timestamps,
                )
            )
        else:
            return None

    def on_enter_requested(self) -> None:
        """
        > The function `on_enter_requested` is called when the state machine enters the `requested` state
        """
        # post CRD object create hook (validation is already run)
        self.post_event(
            self.requested.value,
            f"The cluster request for '{self.name}' has been accepted",
        )

    def on_create(self):
        """
        > The function posts an event to the Kubernetes API, and then patches the custom resource with the namespace
        """
        self.post_event(
            self.creating.value, f"The cluster '{self.name}' is now being created"
        )
        self.custom_api.patch_namespaced_custom_object(
            namespace=self.configuration.NAMESPACE,
            name=self.name,
            body={"beibootNamespace": self.namespace},
            group="getdeck.dev",
            plural="beiboots",
            version="v1",
            async_req=True,
        )

    async def on_enter_creating(self):
        """
        It creates the provider workloads for the cluster, adds additional services, and creates the services
        """
        # create the workloads for this cluster provider
        try:
            handle_create_namespace(self.logger, self.namespace)
            await self.provider.create()
        except k8s.client.ApiException as e:
            try:
                body = json.loads(e.body)
            except JSONDecodeError:
                pass
            else:
                raise kopf.TemporaryError(body.get("message"), delay=5)
            raise kopf.TemporaryError(delay=5)

        # add additional services
        services = []
        additional_services = ports_to_services(
            self.provider.get_ports(), self.namespace, self.parameters
        )
        if additional_services:
            services.extend(additional_services)

        # create the services
        for svc in services:
            self.logger.debug("Creating: " + str(svc))
            handle_create_service(self.logger, svc, self.namespace)

        # also create the tunnel service
        ports = self.provider.get_ports()
        try:
            await handle_ghostunnel_components(
                self.logger,
                port_mappings={"0.0.0.0:6443": "kubeapi:6443"},
                namespace=self.namespace,
                configuration=self.configuration,
            )
        except Exception as e:
            self.logger.error(str(e))

    async def on_boot(self):
        self.post_event(
            self.pending.value,
            f"Now waiting for the cluster '{self.name}' to enter ready state",
        )


    async def on_operate(self):
        """
        If the cluster is running, post the event and return. If the cluster is pending, check if it's been pending for
        longer than the timeout. If it has, raise a permanent error. If it hasn't, raise a temporary error
        """
        if await self.provider.running():
            self.post_event(
                self.running.value, f"The cluster '{self.name}' is now running"
            )

        else:
            # check how long this cluster is pending
            if pending_timestamp := self.completed_transition(
                BeibootCluster.pending.value
            ):
                pending_since = datetime.fromisoformat(pending_timestamp.strip("Z"))
                if datetime.utcnow() - pending_since > timedelta(
                    seconds=self.parameters.clusterReadyTimeout
                ):
                    raise kopf.PermanentError(
                        f"The cluster '{self.name}' did not become running in time "
                        f"(timeout: {self.parameters.clusterReadyTimeout}s)"
                    )
                else:
                    raise kopf.TemporaryError(
                        f"Waiting for cluster '{self.name}' to enter running state",
                        delay=1,
                    )
            else:
                raise kopf.TemporaryError(
                    f"Waiting for cluster '{self.name}' to enter running state", delay=1
                )

    async def on_enter_running(self) -> None:
        """
        It creates the Gefyra service in the namespace of the Beiboot, and adds the endpoint and port to the kubeconfig
        """
        raw_kubeconfig = await self.kubeconfig
        body_patch = {
            "kubeconfig": {
                "source": base64.b64encode(raw_kubeconfig.encode("utf-8")).decode(
                    "utf-8"
                )
            }
        }

        # handle Gefyra integration
        if hasattr(self.parameters, "gefyra") and self.parameters.gefyra.get("enabled"):
            from beiboot.comps.gefyra import handle_gefyra_components

            try:
                (
                    gefyra_nodeport,
                    gefyra_endpoint,
                    raw_kubeconfig,
                ) = await handle_gefyra_components(
                    kubeconfig=raw_kubeconfig,
                    namespace=self.namespace,
                    configuration=self.configuration,
                    cluster_config=self.parameters,
                )
                body_patch = {
                    "gefyra": {"port": gefyra_nodeport, "endpoint": gefyra_endpoint},
                    "kubeconfig": {
                        "source": base64.b64encode(
                            raw_kubeconfig.encode("utf-8")
                        ).decode("utf-8")
                    },
                }
            except Exception as e:
                self.logger.error(f"Could not set up Gefyra: {str(e)}")

        self.custom_api.patch_namespaced_custom_object(
            namespace=self.configuration.NAMESPACE,
            name=self.name,
            body=body_patch,
            group="getdeck.dev",
            plural="beiboots",
            version="v1",
        )

    async def on_reconcile(self) -> None:
        """
        If the cluster is ready, return. If the cluster is not ready, check if it's been ready for longer than the
        timeout. If it has, raise a permanent error. If it hasn't, raise a temporary error
        :return: The return value of the function is ignored.
        """
        if await self.provider.ready():
            if not self.is_ready:
                self.post_event(
                    self.ready.value, f"The cluster '{self.name}' is now ready"
                )
            return
        else:
            # check how long this cluster is not ready
            timestamp_since = self.get_latest_transition()
            if timestamp_since:
                if datetime.utcnow() - timestamp_since > timedelta(
                    seconds=self.parameters.clusterReadyTimeout
                ):
                    raise kopf.PermanentError(
                        f"The cluster infrastructure of '{self.name}' is not ready/running "
                        f"(timeout: {self.parameters.clusterReadyTimeout}s)"
                    )
                else:
                    raise kopf.TemporaryError(
                        "The cluster is currently not in ready state", delay=5
                    )
            else:
                # this should rarely happen; only if running update has not been processed by K8s
                # cannot reconcile cluster that was never in running state
                raise kopf.TemporaryError(delay=1)

    async def on_impair(self, reason: str):
        self.post_event(self.error.value, f"The cluster has become defective: {reason}")

    async def on_recover(self):
        await self.on_reconcile()

    async def on_enter_terminating(self):
        """
        It deletes the provider and then deletes the namespace
        """
        try:
            await self.provider.delete()
        except k8s.client.ApiException:
            pass
        try:
            status = await handle_delete_namespace(self.logger, self.namespace)
            if status.status == "Terminating":
                raise kopf.TemporaryError(
                    f"Namespace {self.namespace} still terminating"
                )
        except k8s.client.ApiException:
            pass

    def on_enter_state(self, *args, **kwargs):
        self._write_state()

    def _get_now(self) -> str:
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
        now = self._get_now()
        event = k8s.client.EventsV1Event(
            metadata=k8s.client.V1ObjectMeta(
                name=f"{self.name}-{uuid.uuid4()}",
                namespace=self.configuration.NAMESPACE,
            ),
            reason=reason.capitalize(),
            note=message[:1024],  # maximum message length
            event_time=now,
            action="Beiboot-State",
            type=_type,
            reporting_instance="beiboot-operator",
            reporting_controller="beiboot-operator",
            regarding=k8s.client.V1ObjectReference(
                kind="beiboot",
                name=self.name,
                namespace=self.configuration.NAMESPACE,
                uid=self.model.metadata["uid"],
            ),
        )
        self.events_api.create_namespaced_event(
            namespace=self.configuration.NAMESPACE, body=event
        )

    def _write_state(self):
        self.custom_api.patch_namespaced_custom_object(
            namespace=self.configuration.NAMESPACE,
            name=self.name,
            body={
                "state": self.current_state.value,
                "stateTransitions": {self.current_state.value: self._get_now()},
            },
            group="getdeck.dev",
            plural="beiboots",
            version="v1",
        )
