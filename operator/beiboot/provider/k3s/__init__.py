import re
from datetime import timedelta
from typing import List

import kopf
import kubernetes as k8s

from beiboot.configuration import BeibootConfiguration, ClusterConfiguration
from beiboot.provider.abstract import AbstractClusterProvider
from beiboot.utils import exec_command_pod, get_label_selector

from .utils import (
    create_k3s_server_workload,
    create_k3s_agent_workload,
    create_k3s_kubeapi_service,
)
from ...resources.utils import handle_delete_statefulset, handle_delete_service

core_api = k8s.client.CoreV1Api()
app_api = k8s.client.AppsV1Api()


class K3s(AbstractClusterProvider):

    provider_type = "k3s"

    def __init__(
        self,
        configuration: BeibootConfiguration,
        cluster_parameter: ClusterConfiguration,
        name: str,
        namespace: str,
        ports: List[str],
        logger,
    ):
        super().__init__(name, namespace, ports)
        self.configuration = configuration
        self.parameters = cluster_parameter
        self.logger = logger

    def _parse_kubectl_nodes_output(self, string: str) -> dict:

        regex = re.compile(
            r"((?P<hours>\d+?)hr)?((?P<minutes>\d+?)m)?((?P<seconds>\d+?)s)?"
        )

        def parse_time(time_str):
            parts = regex.match(time_str)
            if not parts:
                return
            parts = parts.groupdict()
            time_params = {}
            for name, param in parts.items():
                if param:
                    time_params[name] = int(param)
            return timedelta(**time_params)

        result = {}
        for idx, line in enumerate(string.split("\n")):
            if idx == 0 or line == "":
                continue
            name, status, roles, age, version = line.split()
            result[name] = {
                "status": status,
                "roles": roles,
                "age": parse_time(age),
                "version": version,
            }
        return result

    def _remove_cluster_node(self, api_pod_name: str, node_name: str):
        exec_command_pod(
            core_api,
            api_pod_name,
            self.namespace,
            self.parameters.apiServerContainerName,
            ["kubectl", "delete", "node", node_name],
        )

    async def get_kubeconfig(self) -> str:
        try:
            api_pod = core_api.list_namespaced_pod(
                self.namespace,
                label_selector=get_label_selector(self.parameters.serverLabels),
            )
            if len(api_pod.items) != 1:
                self.logger.warning(
                    f"There is more then one API Pod, it is {len(api_pod.items)}"
                )

            kubeconfig = exec_command_pod(
                core_api,
                api_pod.items[0].metadata.name,
                self.namespace,
                self.parameters.apiServerContainerName,
                ["cat", self.parameters.kubeconfigFromLocation],
            )
            if "No such file or directory" in kubeconfig:
                raise kopf.TemporaryError("The kubeconfig is not yet ready.", delay=2)
            else:
                return kubeconfig
        except k8s.client.ApiException as e:
            self.logger.error(str(e))
            raise kopf.TemporaryError("The kubeconfig is not yet ready.", delay=2)

    async def create(self) -> bool:
        from beiboot.utils import generate_token
        from beiboot.resources.utils import (
            handle_create_statefulset,
            handle_create_service,
        )

        node_token = generate_token()
        server_workloads = [
            create_k3s_server_workload(self.namespace, node_token, self.parameters)
        ]
        node_workloads = [
            create_k3s_agent_workload(self.namespace, node_token, self.parameters, node)
            for node in range(
                1, self.parameters.nodes
            )  # (no +1 ) since the server deployment already runs one node
        ]
        services = [create_k3s_kubeapi_service(self.namespace, self.parameters)]

        #
        # Create the workloads
        #
        workloads = server_workloads + node_workloads
        for sts in workloads:
            self.logger.debug("Creating: " + str(sts))
            handle_create_statefulset(self.logger, sts, self.namespace)

        #
        # Create the services
        #
        for svc in services:
            self.logger.debug("Creating: " + str(svc))
            handle_create_service(self.logger, svc, self.namespace)
        return True

    async def delete(self) -> bool:
        try:
            stss = app_api.list_namespaced_stateful_set(
                self.namespace,
                async_req=True,
                label_selector=get_label_selector(self.parameters.nodeLabels),
            )
            for sts in stss.get().items:
                handle_delete_statefulset(
                    logger=self.logger, name=sts.metadata.name, namespace=self.namespace
                )

            volume_claims = core_api.list_namespaced_persistent_volume_claim(
                self.namespace, async_req=True
            )
            for pvc in volume_claims.get().items:
                try:
                    if pvc.spec.volume_name:
                        core_api.delete_persistent_volume(
                            name=pvc.spec.volume_name, grace_period_seconds=0
                        )
                    core_api.delete_namespaced_persistent_volume_claim(
                        name=pvc.metadata.name,
                        namespace=self.namespace,
                        grace_period_seconds=0,
                    )
                except k8s.client.exceptions.ApiException as e:
                    if e.status == 404:
                        continue
                    else:
                        raise e

            service = create_k3s_kubeapi_service(self.namespace, self.parameters)
            handle_delete_service(
                self.logger, name=service.metadata.name, namespace=self.namespace
            )
        except k8s.client.ApiException:
            pass
        return True

    async def exists(self) -> bool:
        raise NotImplementedError

    async def running(self) -> bool:
        # waiting for all StatefulSets to become ready
        try:
            stss = app_api.list_namespaced_stateful_set(
                self.namespace,
                label_selector=get_label_selector(self.parameters.nodeLabels),
            )
            if len(stss.items) == 0:
                return False
            for sts in stss.items:
                if (
                    sts.status.updated_replicas == sts.spec.replicas
                    and sts.status.replicas == sts.spec.replicas  # noqa
                    and sts.status.available_replicas == sts.spec.replicas  # noqa
                    and sts.status.observed_generation
                    >= sts.metadata.generation  # noqa
                ):
                    continue
                else:
                    return False
            else:
                return True
        except k8s.client.ApiException as e:
            self.logger.error(str(e))
            return False

    async def ready(self) -> bool:
        if not await self.running():
            return False

        api_pod = core_api.list_namespaced_pod(
            self.namespace,
            label_selector=get_label_selector(self.parameters.serverLabels),
        )
        if len(api_pod.items) > 1:
            self.logger.warning(
                f"There is more then one API Pod, it is {len(api_pod.items)}"
            )
        elif len(api_pod.items) == 0:
            return False
        else:
            pass

        try:
            output = exec_command_pod(
                core_api,
                api_pod.items[0].metadata.name,
                self.namespace,
                self.parameters.apiServerContainerName,
                ["kubectl", "get", "node"],
            )
            if "No resources found" in output:
                return False
            else:
                node_data = self._parse_kubectl_nodes_output(output)
                _ready = []
                for node in node_data.values():
                    _ready.append(node["status"] == "Ready")
                if all(_ready):
                    return True
                else:
                    # there are unready nodes
                    for name, node in node_data.items():
                        if node["status"] == "Ready":
                            continue
                        else:
                            # wait for a node to become ready within 30 seconds
                            if node["age"].seconds > 30:
                                self._remove_cluster_node(
                                    api_pod.items[0].metadata.name, name
                                )
                return True
        except k8s.client.exceptions.ApiException as e:
            self.logger.error(str(e))
            return False

    def api_version(self) -> str:
        """
        Best return a type that allows working comparisons between versions of the same provider.
        E.g. (1, 10) > (1, 2), but "1.10" < "1.2"
        """
        raise NotImplementedError


class K3sBuilder:
    def __init__(self):
        self._instances = {}

    def __call__(
        self,
        configuration: BeibootConfiguration,
        cluster_parameter: ClusterConfiguration,
        name: str,
        namespace: str,
        ports: List[str],
        logger,
        **_ignored,
    ):
        instance = K3s(
            configuration=configuration,
            cluster_parameter=cluster_parameter,
            name=name,
            namespace=namespace,
            ports=ports,
            logger=logger,
        )
        return instance
