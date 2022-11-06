import re
from datetime import timedelta
from typing import List

import kopf
import kubernetes as k8s

from beiboot.configuration import BeibootConfiguration, ClusterConfiguration
from beiboot.provider.abstract import AbstractClusterProvider
from beiboot.utils import exec_command_pod

from .utils import (
    create_k3s_server_workload,
    create_k3s_agent_workload,
    create_k3s_kubeapi_service,
)

core_api = k8s.client.CoreV1Api()


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

        regex = re.compile(r'((?P<hours>\d+?)hr)?((?P<minutes>\d+?)m)?((?P<seconds>\d+?)s)?')
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
                "version": version
            }
        return result

    def _remove_cluster_node(self, api_pod_name: str,  node_name: str):
        exec_command_pod(
            core_api,
            api_pod_name,
            self.namespace,
            self.parameters.apiServerContainerName,
            ["kubectl", "delete", "node", node_name],
        )



    async def get_kubeconfig(self) -> str:

        selector = ",".join(
            [
                "{0}={1}".format(*label)
                for label in list(self.parameters.serverLabels.items())
            ]
        )
        api_pod = core_api.list_namespaced_pod(
            self.namespace, label_selector=selector
        )
        if len(api_pod.items) != 1:
            self.logger.warning(f"There is more then one API Pod, it is {len(api_pod.items)}")

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

    async def create(self) -> bool:
        from beiboot.utils import generate_token
        from beiboot.resources.utils import (
            handle_create_statefulset,
            handle_create_service,
        )

        node_token = generate_token()
        cgroup = "".join(e for e in self.name if e.isalnum())
        server_workloads = [
            create_k3s_server_workload(
                self.namespace, node_token, cgroup, self.parameters
            )
        ]
        node_workloads = [
            create_k3s_agent_workload(
                self.namespace, node_token, cgroup, self.parameters, node
            )
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
        # Todo force delete pvc, pods
        pass

    async def exists(self) -> bool:
        raise NotImplementedError

    async def running(self) -> bool:
        app_api = k8s.client.AppsV1Api()

        # waiting for all StatefulSets to become ready
        stss = app_api.list_namespaced_stateful_set(self.namespace, async_req=True)
        for sts in stss.get().items:
            if (
                sts.status.updated_replicas == sts.spec.replicas
                and sts.status.replicas == sts.spec.replicas  # noqa
                and sts.status.available_replicas == sts.spec.replicas  # noqa
                and sts.status.observed_generation >= sts.metadata.generation  # noqa
            ):
                continue
            else:
                return False
        else:
            return True

    async def ready(self) -> bool:
        if not await self.running():
            return False

        selector = ",".join(
            [
                "{0}={1}".format(*label)
                for label in list(self.parameters.serverLabels.items())
            ]
        )
        api_pod = core_api.list_namespaced_pod(
            self.namespace, label_selector=selector
        )
        if len(api_pod.items) != 1:
            self.logger.warning(f"There is more then one API Pod, it is {len(api_pod.items)}")

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
                            self._remove_cluster_node(api_pod.items[0].metadata.name, name)
            return True






            return True

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