import base64
import json
import random
import uuid
from asyncio import sleep
from datetime import datetime, timedelta
from json import JSONDecodeError
from typing import Optional

import kubernetes as k8s
import kopf
import yaml

from beiboot.configuration import BeibootConfiguration, ClusterConfiguration
from beiboot.provider.abstract import AbstractClusterProvider
from beiboot.provider.factory import cluster_factory, ProviderType
from beiboot.resources.services import ports_to_services, gefyra_service
from beiboot.resources.utils import (
    handle_create_namespace,
    handle_create_service,
    handle_delete_namespace,
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
        return self.model["metadata"]["name"]

    @property
    def namespace(self) -> str:
        # if the namespace was already persisted to the CRD object, take it from there
        if namespace := self.model.get("beibootNamespace"):
            return namespace
        else:
            # otherwise, generate the name
            from beiboot.utils import get_namespace_name

            return get_namespace_name(self.name, self.parameters)

    @property
    def provider(self) -> AbstractClusterProvider:
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
    async def kubeconfig(self) -> str:
        if source := self.model.get("kubeconfig"):
            if enc_kubeconfig := source.get("source"):
                kubeconfig = base64.b64decode(enc_kubeconfig).decode("utf-8")
            else:
                kubeconfig = await self.provider.get_kubeconfig()
        else:
            kubeconfig = await self.provider.get_kubeconfig()
        return kubeconfig

    def completed_transition(self, state_value: str) -> Optional[str]:
        if transitions := self.model.get("stateTransitions"):
            return transitions.get(state_value, None)
        else:
            return None

    def on_enter_requested(self):
        # post CRD object create hook (validation is already run)
        self.post_event(
            self.requested.value,
            f"The cluster request for '{self.name}' has been accepted",
        )

    def on_create(self):
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
        # todo create service account
        await sleep(1)

    async def on_boot(self):
        self.post_event(
            self.pending.value,
            f"Now waiting for the cluster '{self.name}' to enter ready state",
        )

    async def on_operate(self):
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

    async def on_enter_running(self):
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
            from beiboot.utils import get_external_node_ips
            from beiboot.utils import get_taken_gefyra_ports

            try:
                gefyra_ports = self.parameters.gefyra.get("ports")
                lower_bound = int(gefyra_ports.split("-")[0])
                upper_bound = int(gefyra_ports.split("-")[1])
                taken_ports = get_taken_gefyra_ports(
                    self.custom_api, self.configuration
                )
                gefyra_nodeport = random.choice(
                    [
                        port
                        for port in range(lower_bound, upper_bound + 1)
                        if port not in taken_ports
                    ]
                )
                self.logger.info(f"Requesting Gefyra Nodeport: {gefyra_nodeport}")
                handle_create_service(
                    self.logger,
                    gefyra_service(gefyra_nodeport, self.namespace, self.parameters),
                    self.namespace,
                )
                _ips = get_external_node_ips(self.core_api)
                gefyra_endpoint = _ips[0] if _ips else None
                # return a dict with the source generated by the K8s provider
                # add gefyra connection params to kubeconfig
                if gefyra_endpoint and gefyra_nodeport:
                    data = yaml.safe_load(raw_kubeconfig)
                    for ctx in data["contexts"]:
                        if ctx["name"] == "default":
                            ctx["gefyra"] = f"{gefyra_endpoint}:{gefyra_nodeport}"
                    raw_kubeconfig = yaml.dump(data)
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

    async def on_reconcile(self):
        if await self.provider.ready():
            if self.is_running:
                self.post_event(
                    self.ready.value, f"The cluster '{self.name}' is now ready"
                )
            return
        else:
            # check how long this cluster is not ready
            if running_timestamp := self.completed_transition(
                BeibootCluster.running.value
            ):
                running_since = datetime.fromisoformat(running_timestamp.strip("Z"))
                if datetime.utcnow() - running_since > timedelta(
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

    def post_event(self, reason: str, message: str, _type: str = "Normal"):
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
