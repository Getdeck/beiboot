import kubernetes as k8s

from beiboot.configuration import ClusterConfiguration


def create_k3s_server_workload(
    namespace: str, node_token: str, cluster_config: ClusterConfiguration
) -> k8s.client.V1StatefulSet:
    container = k8s.client.V1Container(
        name=cluster_config.apiServerContainerName,
        image=f"{cluster_config.k3sImage}:{cluster_config.k3sImageTag}",
        image_pull_policy=cluster_config.k3sImagePullPolicy,
        command=["/bin/sh", "-c"],
        args=[
            "k3s server "
            "--https-listen-port=6443 "
            "--write-kubeconfig-mode=0644 "
            "--tls-san=0.0.0.0 "
            "--data-dir /getdeck/data "
            f"--write-kubeconfig={cluster_config.kubeconfigFromLocation} "
            "--cluster-cidr=10.45.0.0/16 "
            "--service-cidr=10.46.0.0/16 "
            "--cluster-dns=10.46.0.10 "
            "--disable-cloud-controller "
            "--disable=traefik "
            f"--agent-token={node_token} "
            "--token=1234"
        ],
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
            requests=cluster_config.serverResources["requests"],
            limits=cluster_config.serverResources["limits"],
        ),
        security_context=k8s.client.V1SecurityContext(
            privileged=True,
            capabilities=k8s.client.V1Capabilities(add=["NET_ADMIN", "SYS_MODULE"]),
        ),
        volume_mounts=[
            k8s.client.V1VolumeMount(
                name="k8s-server-data", mount_path="/getdeck/data"
            ),
        ],
    )

    template = k8s.client.V1PodTemplateSpec(
        metadata=k8s.client.V1ObjectMeta(labels=cluster_config.serverLabels),
        spec=k8s.client.V1PodSpec(
            containers=[container],
        ),
    )

    volume = k8s.client.V1PersistentVolumeClaimTemplate(
        metadata=k8s.client.V1ObjectMeta(name="k8s-server-data"),
        spec=k8s.client.V1PersistentVolumeClaimSpec(
            access_modes=["ReadWriteOnce"],
            resources=k8s.client.V1ResourceRequirements(
                requests={"storage": cluster_config.serverStorageRequests}
            ),
        ),
    )

    spec = k8s.client.V1StatefulSetSpec(
        replicas=1,
        template=template,
        selector={"matchLabels": cluster_config.serverLabels},
        volume_claim_templates=[volume],
        service_name="k3s-server",
    )

    workload = k8s.client.V1StatefulSet(
        api_version="apps/v1",
        metadata=k8s.client.V1ObjectMeta(name="server", namespace=namespace),
        spec=spec,
    )

    return workload


def create_k3s_agent_workload(
    namespace: str,
    node_token: str,
    cluster_config: ClusterConfiguration,
    node_index: int = 1,
) -> k8s.client.V1StatefulSet:
    container = k8s.client.V1Container(
        name="agent",
        image=f"{cluster_config.k3sImage}:{cluster_config.k3sImageTag}",
        image_pull_policy=cluster_config.k3sImagePullPolicy,
        command=["/bin/sh", "-c"],
        args=[
            "k3s agent "
            "-s=https://kubeapi:6443 "
            f"--token={node_token} "
            f"--with-node-id "
        ],
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
            requests=cluster_config.nodeResources["requests"],
            limits=cluster_config.nodeResources["limits"],
        ),
        volume_mounts=[
            k8s.client.V1VolumeMount(
                name=f"k8s-node-data-{node_index}", mount_path="/getdeck/data"
            ),
        ],
    )

    template = k8s.client.V1PodTemplateSpec(
        metadata=k8s.client.V1ObjectMeta(labels=cluster_config.nodeLabels),
        spec=k8s.client.V1PodSpec(
            containers=[container],
        ),
    )

    volume = k8s.client.V1PersistentVolumeClaimTemplate(
        metadata=k8s.client.V1ObjectMeta(name=f"k8s-node-data-{node_index}"),
        spec=k8s.client.V1PersistentVolumeClaimSpec(
            access_modes=["ReadWriteOnce"],
            resources=k8s.client.V1ResourceRequirements(
                requests={"storage": cluster_config.nodeStorageRequests}
            ),
        ),
    )

    spec = k8s.client.V1StatefulSetSpec(
        replicas=1,
        template=template,
        selector={"matchLabels": cluster_config.nodeLabels},
        volume_claim_templates=[volume],
        service_name="k3s-agent",
    )

    workload = k8s.client.V1StatefulSet(
        api_version="apps/v1",
        metadata=k8s.client.V1ObjectMeta(
            name=f"agent-{node_index}", namespace=namespace
        ),
        spec=spec,
    )

    return workload


def create_k3s_kubeapi_service(
    namespace: str, cluster_config: ClusterConfiguration
) -> k8s.client.V1Service:
    spec = k8s.client.V1ServiceSpec(
        type="ClusterIP",
        selector=cluster_config.serverLabels,
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
