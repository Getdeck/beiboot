import logging
from typing import Dict

import kubernetes as k8s

from beiboot.configuration import BeibootConfiguration
from beiboot.resources.utils import handle_create_statefulset
from beiboot.utils import get_external_node_ips

logger = logging.getLogger("beiboot.gefyra")
app_api = k8s.client.AppsV1Api()
core_api = k8s.client.CoreV1Api()

GHOSTUNNEL_NAME = "beiboot-tunnel"


def create_ghostunnel_workload(
    port_mappings: Dict[str, str], namespace: str, configuration: BeibootConfiguration
) -> k8s.client.V1StatefulSet:
    certstrap_init = k8s.client.V1Container(
        name="certstrap-init",
        image=configuration.CERTSTRAP_IMAGE,
        image_pull_policy="IfNotPresent",
        args=["--depot-path", "/out", "init", "--common-name", namespace, "--passphrase", ""],
        volume_mounts=[
            k8s.client.V1VolumeMount(name="pki-data", mount_path="/out"),
        ],
    )
    _ips = get_external_node_ips(core_api)
    certstrap_request_server = k8s.client.V1Container(
        name="certstrap-server-request",
        image=configuration.CERTSTRAP_IMAGE,
        image_pull_policy="IfNotPresent",
        args=["--depot-path", "/out", "request-cert", "server", "--common-name", "server", "--passphrase", "", "-ip", f"{','.join(_ips)}"],
        volume_mounts=[
            k8s.client.V1VolumeMount(name="pki-data", mount_path="/out"),
        ],
    )
    certstrap_request_client = k8s.client.V1Container(
        name="certstrap-client-request",
        image=configuration.CERTSTRAP_IMAGE,
        image_pull_policy="IfNotPresent",
        args=["--depot-path", "/out", "request-cert", "client", "--common-name", "client", "--passphrase", ""],
        volume_mounts=[
            k8s.client.V1VolumeMount(name="pki-data", mount_path="/out"),
        ],
    )
    certstrap_sign_server = k8s.client.V1Container(
        name="certstrap-server-sign",
        image=configuration.CERTSTRAP_IMAGE,
        image_pull_policy="IfNotPresent",
        args=["--depot-path", "/out", "sign", "server", "--CA", namespace],
        volume_mounts=[
            k8s.client.V1VolumeMount(name="pki-data", mount_path="/out"),
        ],
    )
    certstrap_sign_client = k8s.client.V1Container(
        name="certstrap-client-sign",
        image=configuration.CERTSTRAP_IMAGE,
        image_pull_policy="IfNotPresent",
        args=["--depot-path", "/out", "sign", "client", "--CA", namespace],
        volume_mounts=[
            k8s.client.V1VolumeMount(name="pki-data", mount_path="/out"),
        ],
    )

    proxy_containers = []

    for source, target in port_mappings.items():
        port = int(source.split(":")[1])
        container = k8s.client.V1Container(
            name=f"ghostunnel-{port}",
            image=configuration.GHOSTUNNEL_IMAGE,
            image_pull_policy="IfNotPresent",
            args=[
                "server",
                "--listen",
                source,
                "--target",
                target,
                "--unsafe-target",
                "--cacert",
                f"/pki/{namespace}.crt",
                "--cert",
                "/pki/server.crt",
                "--key",
                "/pki/server.key",
                "--allow-cn",
                "client",
            ],
            ports=[
                k8s.client.V1ContainerPort(container_port=port),
            ],
            # todo add requests
            # resources=k8s.client.V1ResourceRequirements(
            #     requests={},
            # ),
            volume_mounts=[
                k8s.client.V1VolumeMount(name="pki-data", mount_path="/pki"),
            ],
        )
        proxy_containers.append(container)

    template = k8s.client.V1PodTemplateSpec(
        metadata=k8s.client.V1ObjectMeta(labels={"beiboot.dev": "tunnel"}),
        spec=k8s.client.V1PodSpec(
            init_containers=[
                certstrap_init,
                certstrap_request_server,
                certstrap_request_client,
                certstrap_sign_server,
                certstrap_sign_client,
            ],
            containers=proxy_containers,
        ),
    )

    volume = k8s.client.V1PersistentVolumeClaimTemplate(
        metadata=k8s.client.V1ObjectMeta(name="pki-data"),
        spec=k8s.client.V1PersistentVolumeClaimSpec(
            access_modes=["ReadWriteOnce"],
            resources=k8s.client.V1ResourceRequirements(requests={"storage": "1M"}),
        ),
    )
    spec = k8s.client.V1StatefulSetSpec(
        replicas=1,
        template=template,
        selector={"matchLabels": {"beiboot.dev": "tunnel"}},
        volume_claim_templates=[volume],
        service_name=GHOSTUNNEL_NAME,
    )

    workload = k8s.client.V1StatefulSet(
        api_version="apps/v1",
        metadata=k8s.client.V1ObjectMeta(name=GHOSTUNNEL_NAME, namespace=namespace),
        spec=spec,
    )
    return workload


async def handle_ghostunnel_components(
    logger,
    port_mappings: Dict[str, str],
    namespace: str,
    configuration: BeibootConfiguration,
):
    try:
        app_api.read_namespaced_stateful_set(name=GHOSTUNNEL_NAME, namespace=namespace)
    except k8s.client.ApiException as e:
        if e.status == 404:
            try:
                sts = create_ghostunnel_workload(
                    port_mappings, namespace, configuration
                )
                handle_create_statefulset(logger, sts, namespace)
            except Exception as e:
                logger.error(e)
                raise e
        else:
            raise e
