import kubernetes as k8s

from beiboot.configuration import configuration


def create_k3s_server_deployment(
    namespace: str, node_token: str, cgroup: str
) -> k8s.client.V1Deployment:
    container = k8s.client.V1Container(
        name=configuration.API_SERVER_CONTAINER_NAME,
        image=f"{configuration.K3S_IMAGE}:{configuration.K3S_IMAGE_TAG}",
        image_pull_policy=configuration.K3S_IMAGE_PULLPOLICY,
        command=["/bin/sh", "-c"],
        args=[
            "k3s server "
            "--https-listen-port=6443 "
            "--write-kubeconfig-mode=0644 "
            "--tls-san=0.0.0.0 "
            f"--write-kubeconfig={configuration.KUBECONFIG_LOCATION} "
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
            requests={"cpu": "0.1", "memory": "100Mi"},
            limits={"cpu": "0.75", "memory": "500Mi"},
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
        metadata=k8s.client.V1ObjectMeta(labels={"app": "server"}),
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
        selector={"matchLabels": {"app": "server"}},
    )

    deployment = k8s.client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=k8s.client.V1ObjectMeta(name="server", namespace=namespace),
        spec=spec,
    )

    return deployment


def create_k3s_agent_deployment(
    namespace: str, node_token: str, cgroup: str
) -> k8s.client.V1Deployment:
    container = k8s.client.V1Container(
        name="agent",
        image=f"{configuration.K3S_IMAGE}:{configuration.K3S_IMAGE_TAG}",
        image_pull_policy=configuration.K3S_IMAGE_PULLPOLICY,
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
        volume_mounts=[
            k8s.client.V1VolumeMount(name="cgroupfs", mount_path="/sys/fs/cgroup"),
            k8s.client.V1VolumeMount(name="modules", mount_path="/lib/modules"),
        ],
    )

    template = k8s.client.V1PodTemplateSpec(
        metadata=k8s.client.V1ObjectMeta(labels={"app": "agent"}),
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
        selector={"matchLabels": {"app": "agent"}},
    )

    deployment = k8s.client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=k8s.client.V1ObjectMeta(name="agent", namespace=namespace),
        spec=spec,
    )

    return deployment


def create_k3s_kubeapi_service(namespace: str) -> k8s.client.V1Service:
    spec = k8s.client.V1ServiceSpec(
        type="ClusterIP",
        selector={"app": "server"},
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
