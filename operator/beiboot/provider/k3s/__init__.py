import re
from datetime import timedelta
from typing import List, Optional, Dict
import urllib

import kopf
import kubernetes as k8s

from beiboot.configuration import BeibootConfiguration, ClusterConfiguration
from beiboot.provider.abstract import AbstractClusterProvider
from beiboot.utils import exec_command_pod, get_label_selector, get_shelf_by_name

from .utils import (
    create_k3s_server_workload,
    create_k3s_agent_workload,
    create_k3s_kubeapi_service,
    PVC_PREFIX_SERVER,
    PVC_PREFIX_NODE
)
from ...resources.utils import handle_delete_statefulset, handle_delete_service, create_volume_snapshots_from_shelf

core_api = k8s.client.CoreV1Api()
app_api = k8s.client.AppsV1Api()
custom_api = k8s.client.CustomObjectsApi()


class K3s(AbstractClusterProvider):

    provider_type = "k3s"

    k3s_image: str = "rancher/k3s"
    k3s_default_image_tag: str = "v1.24.3-k3s1"
    k3s_image_pullpolicy: str = "IfNotPresent"
    kubeconfig_from_location: str = "/getdeck/kube-config.yaml"
    api_server_container_name: str = "apiserver"

    def __init__(
        self,
        configuration: BeibootConfiguration,
        cluster_parameter: ClusterConfiguration,
        name: str,
        namespace: str,
        ports: Optional[List[str]],
        logger,
        shelf_name: str = None,
    ):
        super().__init__(name, namespace, ports, shelf_name)
        self.configuration = configuration
        if shelf_name:
            shelf = get_shelf_by_name(name=shelf_name, api_instance=custom_api, namespace=configuration.NAMESPACE)
            self.shelf = shelf
            cluster_parameter.update(shelf["clusterParameters"])
        else:
            self.shelf = None
        self.parameters = cluster_parameter
        self.logger = logger

    def _check_image_exists(self, k8s_version: str) -> Optional[str]:
        _b = k8s_version.lower().replace("v", "")
        k3s_tag = f"v{_b.strip()}-k3s1"
        req = urllib.request.Request(
            f"https://hub.docker.com/v2/repositories/rancher/k3s/tags/{k3s_tag}",
            method="HEAD",
        )
        try:
            _ = urllib.request.urlopen(req)
            return k3s_tag
        except urllib.error.HTTPError:
            return None

    @property
    def k3s_image_tag(self):
        if k8s_version := self.parameters.k8sVersion:
            tag = self._check_image_exists(k8s_version)
            if tag is None:
                raise kopf.PermanentError(
                    "Cannot create a Beiboot with provider 'k3s' and Kubernetes API version "
                    f"{self.parameters.k8sVersion}"
                )
            return tag
        return self.k3s_default_image_tag

    def _parse_kubectl_nodes_output(self, string: str) -> dict:

        regex = re.compile(
            r"((?P<days>\d+?)d)?((?P<hours>\d+?)h)?((?P<minutes>\d+?)m)?((?P<seconds>\d+?)s)?"
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
            self.api_server_container_name,
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
                self.api_server_container_name,
                ["cat", self.kubeconfig_from_location],
            )
            if "No such file or directory" in kubeconfig:
                raise kopf.TemporaryError("The kubeconfig is not yet ready.", delay=2)
            else:
                return kubeconfig
        except k8s.client.ApiException as e:
            self.logger.error(str(e))
            raise kopf.TemporaryError("The kubeconfig is not yet ready.", delay=2)

    async def create_new(self) -> bool:
        from beiboot.utils import generate_token
        from beiboot.resources.utils import (
            handle_create_statefulset,
            handle_create_service,
        )

        node_token = generate_token()
        server_workloads = [
            create_k3s_server_workload(
                self.namespace,
                node_token,
                self.k3s_image,
                self.k3s_image_tag,
                self.k3s_image_pullpolicy,
                self.kubeconfig_from_location,
                self.api_server_container_name,
                self.parameters,
            )
        ]
        node_workloads = [
            create_k3s_agent_workload(
                self.namespace,
                node_token,
                self.k3s_image,
                self.k3s_image_tag,
                self.k3s_image_pullpolicy,
                self.parameters,
                node,
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

    async def restore_from_shelf(self) -> bool:
        from beiboot.utils import generate_token
        from beiboot.resources.utils import (
            handle_create_statefulset,
            handle_create_service,
        )

        node_to_snapshot_mapping = await create_volume_snapshots_from_shelf(
            self.logger, self.shelf, cluster_namespace=self.namespace
        )

        node_token = generate_token()
        server_workloads = [
            create_k3s_server_workload(
                self.namespace,
                node_token,
                self.k3s_image,
                self.k3s_image_tag,
                self.k3s_image_pullpolicy,
                self.kubeconfig_from_location,
                self.api_server_container_name,
                self.parameters,
                # TODO: what when that doesn't exist?
                node_to_snapshot_mapping["server"]
            )
        ]
        node_workloads = [
            create_k3s_agent_workload(
                self.namespace,
                node_token,
                self.k3s_image,
                self.k3s_image_tag,
                self.k3s_image_pullpolicy,
                self.parameters,
                node,
                # TODO: what when that doesn't exist?
                node_to_snapshot_mapping[f"agent-{node}"]
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
                self.api_server_container_name,
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

    def get_ports(self) -> List[str]:
        """
        Return the published ports
        """
        ports = self.ports
        # add the kubernetes api port for k3s here
        if ports is None:
            ports = ["6443:6443"]
        else:
            ports.append("6443:6443")
        return ports

    async def get_pvc_mapping(self) -> Dict:
        """
        Return a mapping of node-names to the PVC that node uses.

        Example:
        {
            "server": "k8s-server-data-server-0",
            "agent-1": "k8s-node-data-1-agent-1-0",
            "agent-2": "k8s-node-data-2-agent-2-0",
        }
        """
        pods = core_api.list_namespaced_pod(
            self.namespace,
            label_selector=get_label_selector(self.parameters.nodeLabels),
        )
        pvc_mapping = {}
        for pod in pods.items:
            sts_name = pod.metadata.owner_references[0].name
            for volume in pod.spec.volumes:
                try:
                    claim_name = volume.persistent_volume_claim.claim_name
                    if claim_name.startswith(PVC_PREFIX_SERVER) or claim_name.startswith(PVC_PREFIX_NODE):
                        pvc_mapping[sts_name] = claim_name
                except AttributeError:
                    # not every volume as a claim_name
                    continue
        return pvc_mapping

    async def on_shelf_request(self) -> bool:
        """
        Create on demand k3s snapshot on the PVC and prune k3s snapshots, so that only the newly created exists.
        """
        # TODO: can/should we except errors here? Or are we fine that errors propagate and the shelf will permanently
        #  fail if this fails? Interesting: errors of the command that's being run don't cause it to fail
        self.logger.info("K3s.on_shelf_request")
        # we need three calls, as we can't seem to chain commands...
        # ensure directory exists
        resp = exec_command_pod(
            core_api,
            "server-0",
            self.namespace,
            "apiserver",
            [
                "mkdir", "-p", "/getdeck/data/shelf-snapshot"
            ]
        )
        self.logger.info(f"K3s.on_shelf_request mkdir response: {resp}")
        # take k3s snapshot
        resp = exec_command_pod(
            core_api,
            "server-0",
            self.namespace,
            "apiserver",
            [
                "k3s", "etcd-snapshot", "save", "--data-dir", "/getdeck/data", "--dir", "/getdeck/data/shelf-snapshot",
                "--snapshot-compress"
            ]
        )
        self.logger.info(f"K3s.on_shelf_request snapshot response: {resp}")
        # prune k3s snapshots except the most recent one
        resp = exec_command_pod(
            core_api,
            "server-0",
            self.namespace,
            "apiserver",
            [
                "k3s", "etcd-snapshot", "prune", "--data-dir", "/getdeck/data", "--dir", "/getdeck/data/shelf-snapshot",
                "--snapshot-retention", "1"
            ]
        )
        self.logger.info(f"K3s.on_shelf_request prune response: {resp}")


class K3sBuilder:
    def __init__(self):
        self._instances = {}

    def __call__(
        self,
        configuration: BeibootConfiguration,
        cluster_parameter: ClusterConfiguration,
        name: str,
        namespace: str,
        ports: Optional[List[str]],
        logger,
        shelf_name: str = None,
        **_ignored,
    ):
        instance = K3s(
            configuration=configuration,
            cluster_parameter=cluster_parameter,
            name=name,
            namespace=namespace,
            ports=ports,
            logger=logger,
            shelf_name=shelf_name,
        )
        return instance
