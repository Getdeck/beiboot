import json
from typing import Callable

import kubernetes as k8s
from pytest_kubernetes.providers import AClusterManager


def demo_service():
    return k8s.client.V1Service(
        metadata=k8s.client.V1ObjectMeta(name="web"),
        spec=k8s.client.V1ServiceSpec(ports=[k8s.client.V1ServicePort(port=80)]),
    )


def demo_statefulset():
    return k8s.client.V1StatefulSet(
        api_version="apps/v1",
        metadata=k8s.client.V1ObjectMeta(
            name="web",
        ),
        spec=k8s.client.V1StatefulSetSpec(
            replicas=1,
            template=k8s.client.V1PodTemplateSpec(
                metadata=k8s.client.V1ObjectMeta(labels={"app": "nginx"}),
                spec=k8s.client.V1PodSpec(
                    containers=[
                        k8s.client.V1Container(
                            name="nginx",
                            image="registry.k8s.io/nginx-slim:0.8",
                            ports=[
                                k8s.client.V1ContainerPort(
                                    container_port=80, name="web"
                                ),
                            ],
                            volume_mounts=[
                                k8s.client.V1VolumeMount(
                                    name="www", mount_path="/usr/share/nginx/html"
                                ),
                            ],
                        )
                    ],
                ),
            ),
            selector={"matchLabels": {"app": "nginx"}},
            volume_claim_templates=[
                k8s.client.V1PersistentVolumeClaimTemplate(
                    metadata=k8s.client.V1ObjectMeta(name="www"),
                    spec=k8s.client.V1PersistentVolumeClaimSpec(
                        access_modes=["ReadWriteOnce"],
                        resources=k8s.client.V1ResourceRequirements(
                            requests={"storage": "10Mi"}
                        ),
                    ),
                )
            ],
            service_name="nginx",
        ),
    )


def demo_deployment():
    return k8s.client.V1Deployment(
        api_version="apps/v1",
        metadata=k8s.client.V1ObjectMeta(
            name="web",
        ),
        spec=k8s.client.V1DeploymentSpec(
            replicas=1,
            template=k8s.client.V1PodTemplateSpec(
                metadata=k8s.client.V1ObjectMeta(labels={"app": "nginx"}),
                spec=k8s.client.V1PodSpec(
                    containers=[
                        k8s.client.V1Container(
                            name="nginx",
                            image="registry.k8s.io/nginx-slim:0.8",
                            ports=[
                                k8s.client.V1ContainerPort(
                                    container_port=80, name="web"
                                ),
                            ],
                        )
                    ],
                ),
            ),
            selector={"matchLabels": {"app": "nginx"}},
        ),
    )


def get_beiboot_data(beiboot_name: str, k8s: AClusterManager) -> dict:
    output = k8s.kubectl(
        ["-n", "getdeck", "get", "bbt", beiboot_name, "-o", "json"]
    )
    if not output:
        raise RuntimeError("This Beiboot object does not exist or is not readable")
    else:
        return output
