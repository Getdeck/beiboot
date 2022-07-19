import kubernetes as k8s

from beiboot.configuration import configuration, ClusterConfiguration


def create_k3s_server_deployment(
    namespace: str, node_token: str, cgroup: str, cluster_config: ClusterConfiguration
) -> k8s.client.V1Deployment:
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
            f"--write-kubeconfig={cluster_config.kubeconfigFromLocation} "
            "--cluster-cidr=10.45.0.0/16 "
            "--service-cidr=10.46.0.0/16 "
            "--cluster-dns=10.46.0.10 "
            "--disable-agent "
            "--disable-network-policy "
            "--disable-cloud-controller "
            "--disable=metrics-server "
            f"--kubelet-arg=--runtime-cgroups=/{cgroup} "
            f"--kubelet-arg=--kubelet-cgroups=/{cgroup} "
            f"--kubelet-arg=--cgroup-root=/{cgroup} "
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
            )
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
            k8s.client.V1VolumeMount(name="cgroupfs", mount_path="/sys/fs/cgroup"),
            k8s.client.V1VolumeMount(name="modules", mount_path="/lib/modules"),
        ],
    )

    template = k8s.client.V1PodTemplateSpec(
        metadata=k8s.client.V1ObjectMeta(labels=cluster_config.serverLabels),
        spec=k8s.client.V1PodSpec(
            containers=[container],
            volumes=[
                k8s.client.V1Volume(
                    name="cgroupfs",
                    host_path=k8s.client.V1HostPathVolumeSource(
                        path="/sys/fs/cgroup", type="Directory"
                    ),
                ),
                k8s.client.V1Volume(
                    name="modules",
                    host_path=k8s.client.V1HostPathVolumeSource(
                        path="/lib/modules", type="Directory"
                    ),
                ),
            ],
        ),
    )

    spec = k8s.client.V1DeploymentSpec(
        replicas=1,
        template=template,
        selector={"matchLabels": cluster_config.serverLabels},
    )

    deployment = k8s.client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=k8s.client.V1ObjectMeta(name="server", namespace=namespace),
        spec=spec,
    )

    return deployment


def create_k3s_agent_deployment(
    namespace: str,
    node_token: str,
    cgroup: str,
    cluster_config: ClusterConfiguration,
    node_index: int = 1,
) -> k8s.client.V1Deployment:
    container = k8s.client.V1Container(
        name="agent",
        image=f"{cluster_config.k3sImage}:{cluster_config.k3sImageTag}",
        image_pull_policy=cluster_config.k3sImagePullPolicy,
        command=["/bin/sh", "-c"],
        args=[
            f"mkdir /sys/fs/cgroup/cpu,cpuacct/{cgroup} ; "
            f"mkdir /sys/fs/cgroup/memory/{cgroup} ; "
            f"mkdir /sys/fs/cgroup/pids/{cgroup} ; "
            f"mkdir /sys/fs/cgroup/systemd/{cgroup}  ; "
            f"mkdir /sys/fs/cgroup/hugetlb/{cgroup} ; "
            f"mkdir /sys/fs/cgroup/cpu,cpuacct/{cgroup} ; "
            f"mkdir /sys/fs/cgroup/cpuset/{cgroup} ; "
            "k3s agent "
            "-s=https://kubeapi:6443 "
            f"--token={node_token} "
            f"--kubelet-arg=--runtime-cgroups=/{cgroup} "
            f"--kubelet-arg=--kubelet-cgroups=/{cgroup} "
            f"--kubelet-arg=--cgroup-root=/{cgroup} "
            "--with-node-id "
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
            k8s.client.V1VolumeMount(name="cgroupfs", mount_path="/sys/fs/cgroup"),
            k8s.client.V1VolumeMount(name="modules", mount_path="/lib/modules"),
        ],
    )

    template = k8s.client.V1PodTemplateSpec(
        metadata=k8s.client.V1ObjectMeta(labels=cluster_config.nodeLabels),
        spec=k8s.client.V1PodSpec(
            containers=[container],
            volumes=[
                k8s.client.V1Volume(
                    name="cgroupfs",
                    host_path=k8s.client.V1HostPathVolumeSource(
                        path="/sys/fs/cgroup", type="Directory"
                    ),
                ),
                k8s.client.V1Volume(
                    name="modules",
                    host_path=k8s.client.V1HostPathVolumeSource(
                        path="/lib/modules", type="Directory"
                    ),
                ),
            ],
        ),
    )

    spec = k8s.client.V1DeploymentSpec(
        replicas=1,
        template=template,
        selector={"matchLabels": cluster_config.nodeLabels},
    )

    deployment = k8s.client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=k8s.client.V1ObjectMeta(
            name=f"agent-{node_index}", namespace=namespace
        ),
        spec=spec,
    )

    return deployment


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
