import asyncio
import random
from asyncio import sleep

import kubernetes as k8s
import kopf
from statemachine import State

from beiboot.configuration import BeibootConfiguration, ClusterConfiguration
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
    error = AsyncState("Cluster error", value="ERROR")
    terminating = AsyncState("Cluster terminating", value="TERMINATING")

    create = requested.to(creating)
    watch = creating.to(pending)
    operate = pending.to(running)
    recover = error.to(running)
    impair = error.from_(running, pending, creating)
    terminate = terminating.from_(running, error)

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

    @property
    def name(self):
        return self.model.metadata.name

    @property
    def namespace(self):
        # if the namespace was already persisted to the CRD object, take it from there
        if namespace := self.model.get("beibootNamespace"):
            return namespace
        else:
            # otherwise, generate the name
            from beiboot.utils import get_namespace_name

            return get_namespace_name(self.name, self.parameters)

    @property
    def provider(self):
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

    def on_enter_requested(self):
        # post CRD object create hook (validation is already run)
        self._write_object_info(
            self.requested.value, "The cluster request has been accepted"
        )

    def on_create(self):
        self._write_object_info(self.creating.value, "The cluster is now being created")
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
        self.provider.create()

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

    def on_watch(self):
        self._write_object_info(
            self.pending.value, "Now waiting for the cluster to become ready"
        )

    async def on_enter_pending(self):
        loop = asyncio.get_event_loop_policy().get_event_loop()
        from beiboot.utils import check_workload_ready

        cluster_ready = loop.create_task(check_workload_ready(self))

        cluster_ready = await cluster_ready
        if not cluster_ready:
            raise kopf.PermanentError(
                f"The cluster did not become ready in time (timeout: {self.parameters.clusterReadyTimeout}s"
            )

    def on_operate(self):
        self._write_object_info(self.running.value, "The cluster is now running")

    async def on_enter_running(self):
        loop = asyncio.get_event_loop_policy().get_event_loop()
        from beiboot.utils import get_kubeconfig

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

                kubeconfig = loop.create_task(
                    get_kubeconfig(
                        self,
                        self.parameters.gefyra["endpoint"] or gefyra_endpoint,
                        gefyra_nodeport,
                    )
                )
                kubeconfig = await kubeconfig
                body_patch = {
                    "beibootNamespace": self.namespace,
                    "gefyra": {"port": gefyra_nodeport, "endpoint": gefyra_endpoint},
                    "kubeconfig": kubeconfig,
                }
            except Exception as e:
                self.logger.error(f"Could not set up Gefyra: {str(e)}")
                kubeconfig = loop.create_task(get_kubeconfig(self))
                kubeconfig = await kubeconfig
                body_patch = {
                    "beibootNamespace": self.namespace,
                    "kubeconfig": kubeconfig,
                }
        else:
            kubeconfig = loop.create_task(get_kubeconfig(self))
            kubeconfig = await kubeconfig
            body_patch = {"beibootNamespace": self.namespace, "kubeconfig": kubeconfig}

        self.custom_api.patch_namespaced_custom_object(
            namespace=self.configuration.NAMESPACE,
            name=self.name,
            body=body_patch,
            group="getdeck.dev",
            plural="beiboots",
            version="v1",
            async_req=True,
        )

    def on_impair(self, reason: str):
        self._write_object_info(
            self.error.value, f"The cluster has become defective: {reason}"
        )

    def on_enter_error(self):
        pass

    def on_enter_state(self, *args, **kwargs):
        self._write_state()

    def _write_object_info(self, value: str, message: str):
        kopf.info(
            self.model,
            reason=value.capitalize(),
            message=message,
        )

    def _write_state(self):
        self.custom_api.patch_namespaced_custom_object(
            namespace=self.configuration.NAMESPACE,
            name=self.name,
            body={"state": self.current_state.value},
            group="getdeck.dev",
            plural="beiboots",
            version="v1",
            async_req=True,
        )
