import logging

import kubernetes as k8s

from beiboot.configuration import ClusterConfiguration

PVC_PREFIX_NODE = "k8s-node-data"
PVC_PREFIX_SERVER = "k8s-server-data"
PRIORITY = 0

logger = logging.getLogger(__name__)


def create_k3s_server_workload(
    namespace: str,
    node_token: str,
    k3s_image: str,
    k3s_image_tag: str,
    k3s_image_pullpolicy: str,
    kubeconfig_from_location: str,
    api_server_container_name: str,
    parameters: ClusterConfiguration,
    volume_snapshot: str = "",
) -> k8s.client.V1StatefulSet:
    """
    It creates a StatefulSet that runs the k3s server

    :param namespace: The namespace to deploy the server into
    :type namespace: str
    :param node_token: The token that will be used to join the cluster
    :type node_token: str
    :param k3s_image: The image to use for the k3s server
    :type k3s_image: str
    :param k3s_image_tag: str,
    :type k3s_image_tag: str
    :param k3s_image_pullpolicy: The image pull policy for the k3s image
    :type k3s_image_pullpolicy: str
    :param kubeconfig_from_location: The location of the kubeconfig file that will be created by the server
    :type kubeconfig_from_location: str
    :param api_server_container_name: The name of the container that will run the k3s server
    :type api_server_container_name: str
    :param parameters: ClusterConfiguration
    :type parameters: ClusterConfiguration
    :param volume_snapshot: The name of the VolumeSnapshot to use when restoring from a shelf.
    :type volume_snapshot: str
    :return: A V1StatefulSet object
    """
    args = [
        "ls -la /getdeck/data/shelf-snapshot/ && "
        "rm --force /getdeck/data/server/cred/passwd && "
        "rm -r --force /getdeck/data/server/db/etcd && "
        "k3s server "
        "--https-listen-port=6443 "
        "--tls-san=0.0.0.0 "
        "--data-dir /getdeck/data "
        "--cluster-cidr=10.45.0.0/16 "
        "--service-cidr=10.46.0.0/16 "
        "--cluster-dns=10.46.0.10 "
        "--disable-cloud-controller "
        "--disable=traefik "
        f"--agent-token={node_token} "
        "--token=1234 "
        "--cluster-init "
        "--cluster-reset "
        "--cluster-reset-restore-path=/getdeck/data/shelf-snapshot/$(ls /getdeck/data/shelf-snapshot/ | head -1); "
        "rm --force /getdeck/data/server/cred/passwd && "
        "k3s server "
        "--https-listen-port=6443 "
        "--write-kubeconfig-mode=0644 "
        "--tls-san=0.0.0.0 "
        "--data-dir /getdeck/data "
        f"--write-kubeconfig={kubeconfig_from_location} "
        "--cluster-cidr=10.45.0.0/16 "
        "--service-cidr=10.46.0.0/16 "
        "--cluster-dns=10.46.0.10 "
        "--disable-cloud-controller "
        "--disable=traefik "
        f"--agent-token={node_token} "
        "--token=1234 "
    ]
    if parameters.nodes > 1:
        args[0] += " --node-taint node-role.kubernetes.io/control-plane:NoSchedule"
    container = k8s.client.V1Container(
        name=api_server_container_name,
        image=f"{k3s_image}:{k3s_image_tag}",
        image_pull_policy=k3s_image_pullpolicy,
        command=["/bin/sh", "-c"],
        args=args,
        env=[
            k8s.client.V1EnvVar(
                name="POD_IP",
                value_from=k8s.client.V1EnvVarSource(
                    field_ref=k8s.client.V1ObjectFieldSelector(
                        field_path="status.podIP"
                    )
                ),
            ),
        ],
        ports=[
            k8s.client.V1ContainerPort(container_port=6443),
            k8s.client.V1ContainerPort(container_port=6444),
        ],
        resources=k8s.client.V1ResourceRequirements(
            requests=parameters.serverResources["requests"],
            limits=parameters.serverResources["limits"],
        ),
        security_context=k8s.client.V1SecurityContext(
            privileged=True,
            capabilities=k8s.client.V1Capabilities(add=["NET_ADMIN", "SYS_MODULE"]),
        ),
        volume_mounts=[
            k8s.client.V1VolumeMount(
                name=PVC_PREFIX_SERVER, mount_path="/getdeck/data"
            ),
        ],
        readiness_probe=k8s.client.V1Probe(
            _exec=k8s.client.V1ExecAction(
                command=["cat", kubeconfig_from_location],
            ),
            period_seconds=1,
            initial_delay_seconds=1,
        ),
        startup_probe=k8s.client.V1Probe(
            _exec=k8s.client.V1ExecAction(
                command=["cat", kubeconfig_from_location],
            ),
            period_seconds=1,
            failure_threshold=15,
        ),
    )

    if volume_snapshot:
        data_source = {
            "name": volume_snapshot,
            "kind": "VolumeSnapshot",
            "apiGroup": "snapshot.storage.k8s.io",
        }
    else:
        data_source = None
    volume = k8s.client.V1PersistentVolumeClaimTemplate(
        metadata=k8s.client.V1ObjectMeta(name=f"{PVC_PREFIX_SERVER}"),
        spec=k8s.client.V1PersistentVolumeClaimSpec(
            access_modes=["ReadWriteOnce"],
            resources=k8s.client.V1ResourceRequirements(
                requests={"storage": parameters.serverStorageRequests}
            ),
            data_source=data_source,
        ),
    )

    template = k8s.client.V1PodTemplateSpec(
        metadata=k8s.client.V1ObjectMeta(labels=parameters.serverLabels),
        spec=k8s.client.V1PodSpec(
            containers=[container],
            priority=PRIORITY,
        ),
    )

    spec = k8s.client.V1StatefulSetSpec(
        replicas=1,
        template=template,
        selector={"matchLabels": parameters.serverLabels},
        volume_claim_templates=[volume],
        service_name="k3s-server",
    )

    workload = k8s.client.V1StatefulSet(
        api_version="apps/v1",
        metadata=k8s.client.V1ObjectMeta(
            name="server", namespace=namespace, labels=parameters.serverLabels
        ),
        spec=spec,
    )

    return workload


def create_k3s_agent_workload(
    namespace: str,
    node_token: str,
    k3s_image: str,
    k3s_image_tag: str,
    k3s_image_pullpolicy: str,
    parameters: ClusterConfiguration,
    node_index: int = 1,
    volume_snapshot: str = "",
) -> k8s.client.V1StatefulSet:
    """
    It creates a Kubernetes StatefulSet that runs the k3s agent

    :param namespace: The namespace to deploy the workload to
    :type namespace: str
    :param node_token: The token that the agent will use to connect to the server
    :type node_token: str
    :param k3s_image: The image to use for the k3s agent
    :type k3s_image: str
    :param k3s_image_tag: The version of k3s to use
    :type k3s_image_tag: str
    :param k3s_image_pullpolicy: The image pull policy for the k3s image
    :type k3s_image_pullpolicy: str
    :param parameters: ClusterConfiguration
    :type parameters: ClusterConfiguration
    :param node_index: The index of the node. This is used to create a unique name for the node, defaults to 1
    :type node_index: int (optional)
    :param volume_snapshot: The name of the VolumeSnapshot to use when restoring from a shelf.
    :type volume_snapshot: str
    """
    container = k8s.client.V1Container(
        name="agent",
        image=f"{k3s_image}:{k3s_image_tag}",
        image_pull_policy=k3s_image_pullpolicy,
        command=["/bin/sh", "-c"],
        args=["k3s agent " "-s=https://kubeapi:6443 " f"--token={node_token} "],
        env=[
            k8s.client.V1EnvVar(
                name="POD_IP",
                value_from=k8s.client.V1EnvVarSource(
                    field_ref=k8s.client.V1ObjectFieldSelector(
                        field_path="status.podIP"
                    )
                ),
            )
        ],
        ports=[
            k8s.client.V1ContainerPort(container_port=6443, protocol="TCP"),
            k8s.client.V1ContainerPort(container_port=6444, protocol="TCP"),
        ],
        security_context=k8s.client.V1SecurityContext(
            privileged=True,
            capabilities=k8s.client.V1Capabilities(add=["NET_ADMIN", "SYS_MODULE"]),
        ),
        resources=k8s.client.V1ResourceRequirements(
            requests=parameters.nodeResources["requests"],
            limits=parameters.nodeResources["limits"],
        ),
        volume_mounts=[
            k8s.client.V1VolumeMount(
                name=f"{PVC_PREFIX_NODE}-{node_index}", mount_path="/getdeck/data"
            ),
        ],
    )

    if volume_snapshot:
        data_source = {
            "name": volume_snapshot,
            "kind": "VolumeSnapshot",
            "apiGroup": "snapshot.storage.k8s.io",
        }
    else:
        data_source = None
    volume = k8s.client.V1PersistentVolumeClaimTemplate(
        metadata=k8s.client.V1ObjectMeta(name=f"{PVC_PREFIX_NODE}-{node_index}"),
        spec=k8s.client.V1PersistentVolumeClaimSpec(
            access_modes=["ReadWriteOnce"],
            resources=k8s.client.V1ResourceRequirements(
                requests={"storage": parameters.nodeStorageRequests}
            ),
            data_source=data_source,
        ),
    )

    template = k8s.client.V1PodTemplateSpec(
        metadata=k8s.client.V1ObjectMeta(labels=parameters.nodeLabels),
        spec=k8s.client.V1PodSpec(
            containers=[container],
            priority=PRIORITY,
        ),
    )

    spec = k8s.client.V1StatefulSetSpec(
        replicas=1,
        template=template,
        selector={"matchLabels": parameters.nodeLabels},
        volume_claim_templates=[volume],
        service_name="k3s-agent",
    )

    workload = k8s.client.V1StatefulSet(
        api_version="apps/v1",
        metadata=k8s.client.V1ObjectMeta(
            name=f"agent-{node_index}",
            namespace=namespace,
            labels=parameters.nodeLabels,
        ),
        spec=spec,
    )

    return workload


def create_k3s_kubeapi_service(
    namespace: str, parameters: ClusterConfiguration
) -> k8s.client.V1Service:
    spec = k8s.client.V1ServiceSpec(
        type="ClusterIP",
        selector=parameters.serverLabels,
        ports=[
            k8s.client.V1ServicePort(
                name="api-tcp", target_port=6443, port=6443, protocol="TCP"
            ),
            k8s.client.V1ServicePort(
                name="api-udp", target_port=6443, port=6443, protocol="UDP"
            ),
        ],
    )

    service = k8s.client.V1Service(
        api_version="v1",
        kind="Service",
        metadata=k8s.client.V1ObjectMeta(name="kubeapi", namespace=namespace),
        spec=spec,
    )

    return service


def create_k3d_pod_distuption_budget(
    namespace: str,
) -> list[k8s.client.V1PodDisruptionBudget]:
    pdbs = []
    spec = k8s.client.V1PodDisruptionBudgetSpec(
        max_unavailable=0,
        selector={"matchLabels": {"beiboot.getdeck.dev/is-node": "true"}},
    )
    pdb_k3s = k8s.client.V1PodDisruptionBudget(
        metadata=k8s.client.V1ObjectMeta(name="BeibootNodeBudget", namespace=namespace), spec=spec
    )
    pdbs.append(pdb_k3s)

    spec = k8s.client.V1PodDisruptionBudgetSpec(
        min_available=1, selector={"matchLabels": {"beiboot.dev": "tunnel"}}
    )
    pdb_tunnel = k8s.client.V1PodDisruptionBudget(
        metadata=k8s.client.V1ObjectMeta(name="BeibootTunnelBudget", namespace=namespace), spec=spec
    )
    pdbs.append(pdb_tunnel)
    return pdbs
