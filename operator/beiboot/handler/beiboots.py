import asyncio

import kopf
import kubernetes as k8s

from beiboot.configuration import configuration
from beiboot.resources.k3s import (
    create_k3s_server_deployment,
    create_k3s_agent_deployment,
    create_k3s_kubeapi_service,
)
from beiboot.utils import generate_token, check_deployment_ready, get_kubeconfig
from beiboot.resources.services import ports_to_services

core_v1_api = k8s.client.CoreV1Api()
app_v1_api = k8s.client.AppsV1Api()
events_v1_api = k8s.client.EventsV1Api()
custom_api = k8s.client.CustomObjectsApi()


def handle_create_namespace(logger, name) -> str:
    namespace = f"{configuration.CLUSTER_NAMESPACE_PREFIX}-{name}"
    try:
        core_v1_api.create_namespace(
            body=k8s.client.V1Namespace(
                metadata=k8s.client.V1ObjectMeta(name=namespace)
            )
        )
        logger.info(f"Created namespace for beiboot: {namespace}")
    except k8s.client.exceptions.ApiException as e:
        if e.status in [409, 422]:
            logger.warn(f"Namespace for beiboot {namespace} already exists")
        else:
            raise e
    return namespace


def handle_delete_deployment(
    logger, deployment: k8s.client.V1Deployment, namespace: str
) -> None:
    try:
        app_v1_api.create_namespaced_deployment(body=deployment, namespace=namespace)
        logger.info(f"Deployment {deployment.metadata.name} created")
    except k8s.client.exceptions.ApiException as e:
        if e.status == 409:
            logger.warn(
                f"Deployment {deployment.metadata.name} already available, now patching it with current configuration"
            )
            app_v1_api.patch_namespaced_deployment(
                name=deployment.metadata.name,
                body=deployment,
                namespace=namespace,
            )
            logger.info(f"Deployment {deployment.metadata.name} patched")
        else:
            raise e


def handle_create_service(
    logger, service: k8s.client.V1Service, namespace: str
) -> None:
    try:
        core_v1_api.create_namespaced_service(body=service, namespace=namespace)
        logger.info(f"Service {service.metadata.name} created")
    except k8s.client.exceptions.ApiException as e:
        if e.status in [409, 422]:
            # the Stowaway service already exist
            # status == 422 is nodeport already allocated
            logger.warn(
                f"Service {service.metadata.name} already available, now patching it with current configuration"
            )
            core_v1_api.patch_namespaced_service(
                name=service.metadata.name,
                body=service,
                namespace=namespace,
            )
            logger.info(f"Service {service.metadata.name} patched")
        else:
            raise e


def handle_delete_namespace(logger, namespace) -> None:
    try:
        core_v1_api.delete_namespace(namespace)
        logger.info(f"Deleted namespace for beiboot: {namespace}")
    except k8s.client.exceptions.ApiException:
        pass


@kopf.on.create("beiboot")
async def beiboot_created(body, logger, **kwargs):
    provider = body.get("provider")  # k3s
    name = body["metadata"]["name"]
    ports = body.get("ports")

    #
    # Create the target namespace
    #
    namespace = handle_create_namespace(logger, name)

    if provider == "k3s":
        node_token = generate_token()
        cgroup = "".join(e for e in name if e.isalnum())
        deployments = [
            create_k3s_server_deployment(namespace, node_token, cgroup),
            create_k3s_agent_deployment(namespace, node_token, cgroup),
        ]
        services = [create_k3s_kubeapi_service(namespace)]
    else:
        raise RuntimeError(
            f"Cannot create Beiboot wit provider {provider}: not supported."
        )

    # check if beiboot exists, handle that case

    #
    # ports to service
    #
    additional_services = ports_to_services(ports, namespace)
    if additional_services:
        services.extend(additional_services)

    #
    # Create the deployments
    #
    for deploy in deployments:
        handle_delete_deployment(logger, deploy, namespace)

    #
    # Create the services
    #
    for svc in services:
        handle_create_service(logger, svc, namespace)

    #
    # schedule startup tasks, work on them async
    #
    loop = asyncio.get_event_loop_policy().get_event_loop()
    aw_api_server_ready = loop.create_task(check_deployment_ready(deployments[0]))
    cluster_ready = loop.create_task(
        get_kubeconfig(aw_api_server_ready, deployments[0])
    )
    kubeconfig = await cluster_ready

    custom_api.patch_namespaced_custom_object(
        namespace=configuration.NAMESPACE,
        name=body.metadata.name,
        body={"beibootNamespace": namespace, "kubeconfig": kubeconfig},
        group="getdeck.dev",
        plural="beiboots",
        version="v1",
    )

    kopf.info(
        body,
        reason="Created",
        message=f"The Beiboot {body['metadata']['name']} has been created",
    )


@kopf.on.delete("beiboot")
async def beiboot_deleted(body, logger, **kwargs):
    namespace = body.get("beibootNamespace")
    handle_delete_namespace(logger, namespace)

    kopf.info(
        body,
        reason="Removed",
        message=f"The Beiboot {body['metadata']['name']} has been removed",
    )
