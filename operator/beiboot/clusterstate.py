import base64
import random
import uuid
from asyncio import sleep
from datetime import datetime

import kubernetes as k8s
import kopf
import yaml
from statemachine import State

from beiboot.configuration import BeibootConfiguration, ClusterConfiguration
from beiboot.provider.abstract import AbstractClusterProvider
from beiboot.provider.factory import cluster_factory, ProviderType
from beiboot.resources.services import ports_to_services, gefyra_service
from beiboot.resources.utils import handle_create_namespace, handle_create_service
from beiboot.utils import StateMachine, AsyncState


class BeibootCluster(StateMachine):
    """
    A Beiboot cluster is implemented as a state machine
    The body of the Beiboot CRD is available as self.model
    """

    requested = State("Cluster requested", initial=True, value="REQUESTED")
    creating = AsyncState("Cluster creating", value="CREATING")
    pending = AsyncState("Cluster pending", value="PENDING")
    running = AsyncState("Cluster running", value="RUNNING")
    ready = AsyncState("Cluster running", value="READY")
    error = AsyncState("Cluster error", value="ERROR")
    terminating = AsyncState("Cluster terminating", value="TERMINATING")

    create = requested.to(creating)
    boot = creating.to(pending)
    operate = pending.to(running)
    reconcile = running.to(ready) | ready.to.itself() | error.to(ready)
    recover = error.to(running)
    impair = error.from_(ready, running, pending, creating, requested)
    terminate = terminating.from_(requested, creating, running, ready, error)

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

    def on_enter_requested(self):
        # post CRD object create hook (validation is already run)
        self.post_event(self.requested.value, "The cluster request has been accepted")

    def on_create(self):
        self.post_event(self.creating.value, "The cluster is now being created")
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
        handle_create_namespace(self.logger, self.namespace)

        # create the workloads for this cluster provider
        await self.provider.create()

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
            self.pending.value, "Now waiting for the cluster to become ready"
        )

    async def on_enter_pending(self):
        from beiboot.utils import check_workload_ready

        cluster_ready = await check_workload_ready(self)
        if not cluster_ready:
            raise kopf.PermanentError(
                f"The cluster did not become ready in time (timeout: {self.parameters.clusterReadyTimeout}s)"
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
            async_req=True,
        )
        self.post_event(self.running.value, "The cluster is now running")

    async def on_reconcile(self):
        from beiboot.utils import check_workload_ready

        cluster_ready = await check_workload_ready(self, silent=True)
        if not cluster_ready:
            raise kopf.PermanentError(
                f"The cluster infrastructure is not ready/running (timeout: {self.parameters.clusterReadyTimeout}s)"
            )
        if not await self.provider.ready():
            raise kopf.TemporaryError(
                "The cluster is currently not in ready state", delay=5
            )
        if self.is_running:
            self.post_event(self.ready.value, "The cluster is now ready")

    async def on_impair(self, reason: str):
        self.post_event(self.error.value, f"The cluster has become defective: {reason}")

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
            note=message,
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
            body={"state": self.current_state.value},
            group="getdeck.dev",
            plural="beiboots",
            version="v1",
        )
