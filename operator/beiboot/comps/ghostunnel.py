import logging
from typing import Dict

import kopf
import kubernetes as k8s

from beiboot.configuration import BeibootConfiguration
from beiboot.resources.utils import handle_create_statefulset, handle_create_service
from beiboot.utils import get_external_node_ips, get_label_selector, exec_command_pod

logger = logging.getLogger("beiboot.ghostunnel")
app_api = k8s.client.AppsV1Api()
core_api = k8s.client.CoreV1Api()

GHOSTUNNEL_NAME = "beiboot-tunnel"
GHOSTUNNEL_LABELS = {"beiboot.dev": "tunnel"}
GHOSTUNNEL_PROBE_PORT = 61535
GHOSTUNNEL_DEPOT = "/pki"


def ghostunnel_service(port: int, namespace: str) -> k8s.client.V1Service:
    spec = k8s.client.V1ServiceSpec(
        type="NodePort",
        selector=GHOSTUNNEL_LABELS,
        ports=[
            k8s.client.V1ServicePort(
                name=f"{port}-tunnel",
                target_port=port,
                port=port,
                protocol="TCP",
            ),
        ],
    )
    service = k8s.client.V1Service(
        api_version="v1",
        kind="Service",
        metadata=k8s.client.V1ObjectMeta(
            name=f"{GHOSTUNNEL_NAME}-{port}",
            namespace=namespace,
            labels=GHOSTUNNEL_LABELS,
        ),
        spec=spec,
    )
    return service


def create_ghostunnel_workload(
    port_mappings: Dict[str, str], namespace: str, configuration: BeibootConfiguration
) -> k8s.client.V1StatefulSet:
    certstrap_init = k8s.client.V1Container(
        name="certstrap-init",
        image=configuration.CERTSTRAP_IMAGE,
        image_pull_policy="IfNotPresent",
        args=[
            "--depot-path",
            "/out",
            "init",
            "--common-name",
            namespace,
            "--passphrase",
            "",
        ],
        volume_mounts=[
            k8s.client.V1VolumeMount(name="pki-data", mount_path="/out"),
        ],
    )
    _ips = get_external_node_ips(core_api)
    certstrap_request_server = k8s.client.V1Container(
        name="certstrap-server-request",
        image=configuration.CERTSTRAP_IMAGE,
        image_pull_policy="IfNotPresent",
        args=[
            "--depot-path",
            "/out",
            "request-cert",
            "server",
            "--common-name",
            "server",
            "--passphrase",
            "",
            "-ip",
            f"{','.join(_ips)}",
        ],
        volume_mounts=[
            k8s.client.V1VolumeMount(name="pki-data", mount_path="/out"),
        ],
    )
    certstrap_request_client = k8s.client.V1Container(
        name="certstrap-client-request",
        image=configuration.CERTSTRAP_IMAGE,
        image_pull_policy="IfNotPresent",
        args=[
            "--depot-path",
            "/out",
            "request-cert",
            "client",
            "--common-name",
            "client",
            "--passphrase",
            "",
        ],
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
                f"{GHOSTUNNEL_DEPOT}/{namespace}.crt",
                "--cert",
                f"{GHOSTUNNEL_DEPOT}/server.crt",
                "--key",
                f"{GHOSTUNNEL_DEPOT}/server.key",
                "--allow-cn",
                "client",
                "--status",
                f"http://0.0.0.0:{GHOSTUNNEL_PROBE_PORT}",
            ],
            ports=[
                k8s.client.V1ContainerPort(container_port=port),
                k8s.client.V1ContainerPort(container_port=GHOSTUNNEL_PROBE_PORT),
            ],
            resources=k8s.client.V1ResourceRequirements(
                requests={"cpu": "0.1", "memory": "16Mi"},
                limits={"memory": "32Mi"},
            ),
            readiness_probe=k8s.client.V1Probe(
                http_get=k8s.client.V1HTTPGetAction(
                    port=GHOSTUNNEL_PROBE_PORT, path="/_status"
                ),
                period_seconds=1,
                initial_delay_seconds=1,
            ),
            volume_mounts=[
                k8s.client.V1VolumeMount(name="pki-data", mount_path=GHOSTUNNEL_DEPOT),
            ],
        )
        proxy_containers.append(container)

    template = k8s.client.V1PodTemplateSpec(
        metadata=k8s.client.V1ObjectMeta(labels=GHOSTUNNEL_LABELS),
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
        selector={"matchLabels": GHOSTUNNEL_LABELS},
        volume_claim_templates=[volume],
        service_name=GHOSTUNNEL_NAME,
    )

    workload = k8s.client.V1StatefulSet(
        api_version="apps/v1",
        metadata=k8s.client.V1ObjectMeta(
            name=GHOSTUNNEL_NAME, namespace=namespace, labels=GHOSTUNNEL_LABELS
        ),
        spec=spec,
    )
    return workload


async def handle_ghostunnel_components(
    port_mappings: Dict[str, str],  # source, target
    namespace: str,
    configuration: BeibootConfiguration,
) -> None:
    try:
        app_api.read_namespaced_stateful_set(name=GHOSTUNNEL_NAME, namespace=namespace)
    except k8s.client.ApiException as e:
        if e.status == 404:
            try:
                logger.info("Creating ghostunnel mTLS")
                sts = create_ghostunnel_workload(
                    port_mappings, namespace, configuration
                )
                handle_create_statefulset(logger, sts, namespace)
                nodeport_services = []
                for source, _ in port_mappings.items():
                    port = source.split(":")[1]
                    if int(port) == GHOSTUNNEL_PROBE_PORT:
                        logger.error(
                            f"Cannot create port forwarding for port {port} as this one is reserved"
                        )
                    else:
                        nodeport_services.append(
                            ghostunnel_service(int(port), namespace)
                        )
                for nodeport_service in nodeport_services:
                    logger.info(
                        f"Requesting tunnel Nodeport: {nodeport_service.metadata.name}"
                    )
                    handle_create_service(logger, nodeport_service, namespace)
            except Exception as e:
                logger.error(e)
                raise e
        else:
            raise e


async def ghostunnel_ready(namespace: str) -> bool:
    labels = get_label_selector(GHOSTUNNEL_LABELS)
    try:
        stss = app_api.list_namespaced_stateful_set(
            namespace,
            label_selector=labels,
        )
        if len(stss.items) == 0:
            return False
        for sts in stss.items:
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
    except k8s.client.ApiException as e:
        logger.error(str(e))
        return False


async def extract_client_tls(namespace: str) -> dict[str, str]:
    labels = get_label_selector(GHOSTUNNEL_LABELS)
    try:
        tunnel_pods = core_api.list_namespaced_pod(
            namespace,
            label_selector=labels,
        )
        if len(tunnel_pods.items) != 1:
            logger.warning(
                f"There is more then one API Pod, it is {len(tunnel_pods.items)}"
            )
        tunnel_pod = tunnel_pods.items[0]
        # we can use the first container, as all running container sharing the same volume containing the PKI
        _container = tunnel_pod.spec.containers[0]

        files = {}
        for filename in ["client.crt", "client.key", f"{namespace}.crt"]:
            content = exec_command_pod(
                core_api,
                tunnel_pod.metadata.name,
                namespace,
                _container.name,
                ["cat", f"{GHOSTUNNEL_DEPOT}/{filename}"],
            )
            if "No such file or directory" in content:
                raise kopf.TemporaryError(
                    f"The tunnel certificate {filename} is not yet ready.", delay=2
                )
            else:
                if filename == f"{namespace}.crt":
                    files["ca.crt"] = content
                else:
                    files[filename] = content
        else:
            return files

    except k8s.client.ApiException as e:
        logger.error(e)
        raise kopf.TemporaryError("The beiboot tunnel is not yet ready.", delay=2)
