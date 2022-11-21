import logging
from typing import Optional, Tuple

import kopf
import kubernetes as k8s

from beiboot.configuration import BeibootConfiguration, ClusterConfiguration
from beiboot.resources.utils import handle_create_service, handle_create_deployment
from beiboot.utils import get_external_node_ips, get_label_selector, exec_command_pod

logger = logging.getLogger("beiboot.ghostunnel")
app_api = k8s.client.AppsV1Api()
core_api = k8s.client.CoreV1Api()

GHOSTUNNEL_NAME = "beiboot-tunnel"
GHOSTUNNEL_LABELS = {"beiboot.dev": "tunnel"}
GHOSTUNNEL_PROBE_PORT = 61535
GHOSTUNNEL_DEPOT = "/pki"


def _ghostunnel_service_mapping(svc: k8s.client.V1Service) -> Tuple[str, str]:
    port = svc.spec.ports[0].port
    return f"0.0.0.0:{port}", f"{svc.metadata.name}:{port}"


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
    port_mappings: list[Tuple[str, str]],
    namespace: str,
    configuration: BeibootConfiguration,
    parameters: ClusterConfiguration,
) -> k8s.client.V1Deployment:
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
    _endpoint = parameters.tunnel.get("endpoint")
    if _endpoint:
        _ips.append(_endpoint)
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

    for idx, mapping in enumerate(port_mappings):
        source, target = mapping
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
                f"http://localhost:{GHOSTUNNEL_PROBE_PORT + idx}",
            ],
            ports=[
                k8s.client.V1ContainerPort(container_port=port),
                k8s.client.V1ContainerPort(container_port=GHOSTUNNEL_PROBE_PORT + idx),
            ],
            resources=k8s.client.V1ResourceRequirements(
                requests={"cpu": "0.1", "memory": "16Mi"},
                limits={"memory": "32Mi"},
            ),
            readiness_probe=k8s.client.V1Probe(
                _exec=k8s.client.V1ExecAction(
                    command=["sh", "-c", f"curl http://localhost:{GHOSTUNNEL_PROBE_PORT + idx}/_status 2>/dev/null | grep listening"]
                ),
                period_seconds=2,
                initial_delay_seconds=5,
            ),
            startup_probe=k8s.client.V1Probe(
                _exec=k8s.client.V1ExecAction(
                    command=["sh", "-c", f"curl http://localhost:{GHOSTUNNEL_PROBE_PORT + idx}/_status 2>/dev/null | grep listening"]
                ),
                period_seconds=2,
                failure_threshold=10,
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
            volumes=[
                k8s.client.V1Volume(
                    name="pki-data", empty_dir=k8s.client.V1EmptyDirVolumeSource()
                )
            ],
        ),
    )

    spec = k8s.client.V1DeploymentSpec(
        replicas=1,
        template=template,
        selector={"matchLabels": GHOSTUNNEL_LABELS},
    )

    workload = k8s.client.V1Deployment(
        api_version="apps/v1",
        metadata=k8s.client.V1ObjectMeta(
            name=GHOSTUNNEL_NAME, namespace=namespace, labels=GHOSTUNNEL_LABELS
        ),
        spec=spec,
    )
    return workload


async def handle_ghostunnel_components(
    expose_services: list[k8s.client.V1Service],
    namespace: str,
    configuration: BeibootConfiguration,
    parameters: ClusterConfiguration,
) -> None:

    _mappings = list(map(_ghostunnel_service_mapping, expose_services))
    logger.info("Creating ghostunnel mTLS")
    deploy = create_ghostunnel_workload(_mappings, namespace, configuration, parameters)
    handle_create_deployment(logger, deploy, namespace)

    # creating multiple services, must be handled appropriately
    nodeport_services = []
    for mapping in _mappings:
        source, target = mapping
        port = source.split(":")[1]
        if int(port) in range(
            GHOSTUNNEL_PROBE_PORT, GHOSTUNNEL_PROBE_PORT + len(_mappings)
        ):
            logger.error(
                f"Cannot create tunnel service for port {port} as this one is reserved"
            )
        else:
            nodeport_services.append(ghostunnel_service(int(port), namespace))
    for nodeport_service in nodeport_services:
        logger.info(f"Requesting tunnel Nodeport: {nodeport_service.metadata.name}")
        handle_create_service(logger, nodeport_service, namespace)


async def remove_ghostunnel_components(namespace: str) -> None:
    try:
        app_api.delete_namespaced_stateful_set(
            namespace=namespace, name=GHOSTUNNEL_NAME
        )
    except k8s.client.ApiException:
        pass
    try:
        svcs = core_api.list_namespaced_service(
            namespace=namespace, label_selector=get_label_selector(GHOSTUNNEL_LABELS)
        )
        for svc in svcs.items:
            core_api.delete_namespaced_service(
                namespace=namespace, name=svc.metadata.name
            )
    except k8s.client.ApiException:
        pass


async def ghostunnel_ready(namespace: str) -> bool:
    labels = get_label_selector(GHOSTUNNEL_LABELS)
    try:
        deploys = app_api.list_namespaced_deployment(
            namespace,
            label_selector=labels,
        )
        if len(deploys.items) == 0:
            return False
        for deploy in deploys.items:
            if (
                deploy.status.updated_replicas == deploy.spec.replicas
                and deploy.status.replicas == deploy.spec.replicas  # noqa
                and deploy.status.available_replicas == deploy.spec.replicas  # noqa
                and deploy.status.observed_generation >= deploy.metadata.generation  # noqa
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


async def get_tunnel_nodeports(
    namespace: str, parameters: ClusterConfiguration
) -> Optional[list[dict]]:
    node_mappings = []
    try:
        services = core_api.list_namespaced_service(
            namespace=namespace, label_selector=get_label_selector(GHOSTUNNEL_LABELS)
        )
        for service in services.items:
            tunnel_endpoint = parameters.tunnel.get("endpoint")
            if bool(tunnel_endpoint) is False:
                _ips = get_external_node_ips(core_api)
                tunnel_endpoint = _ips[0] if _ips else None
            node_mappings.append(
                {
                    "endpoint": f"{tunnel_endpoint}:{service.spec.ports[0].node_port}",
                    "target": service.spec.ports[0].target_port,
                }
            )
    except k8s.client.ApiException as e:
        logger.error(e)
        return []
    return node_mappings
