import asyncio
import traceback
import random

import kopf
import kubernetes as k8s

from beiboot.configuration import configuration
from beiboot.resources.k3s import (
    create_k3s_server_workload,
    create_k3s_agent_workload,
    create_k3s_kubeapi_service,
)
from beiboot.utils import (
    generate_token,
    check_workload_ready,
    get_kubeconfig,
    get_taken_gefyra_ports,
    get_external_node_ips,
)
from beiboot.resources.services import ports_to_services, gefyra_service

from beiboot.configuration import ClusterConfiguration

core_v1_api = k8s.client.CoreV1Api()
app_v1_api = k8s.client.AppsV1Api()
events_v1_api = k8s.client.EventsV1Api()
custom_api = k8s.client.CustomObjectsApi()


def handle_create_namespace(logger, name, cluster_config: ClusterConfiguration) -> str:
    namespace = f"{cluster_config.namespacePrefix}-{name}"
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


def handle_create_statefulset(
    logger, statefulset: k8s.client.V1StatefulSet, namespace: str
) -> None:
    try:
        app_v1_api.create_namespaced_stateful_set(body=statefulset, namespace=namespace)
        logger.info(f"Statefulset {statefulset.metadata.name} created")
    except k8s.client.exceptions.ApiException as e:
        if e.status == 409:
            logger.warn(
                f"Statefulset {statefulset.metadata.name} already available, now patching it with current configuration"
            )
            app_v1_api.patch_namespaced_stateful_set(
                name=statefulset.metadata.name,
                body=statefulset,
                namespace=namespace,
            )
            logger.info(f"Statefulset {statefulset.metadata.name} patched")
        else:
            raise e
    except ValueError as e:
        logger.info(str(e))
        pass


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

    cluster_config = configuration.refresh_k8s_config()
    namespace = cluster_config.namespacePrefix
    #
    # Create the target namespace
    #
    try:
        namespace = handle_create_namespace(logger, name, cluster_config)

        if provider == "k3s":
            node_token = generate_token()
            server_workloads = [
                create_k3s_server_workload(namespace, node_token, cluster_config)
            ]
            node_workloads = [
                create_k3s_agent_workload(namespace, node_token, cluster_config, node)
                for node in range(
                    1, cluster_config.nodes
                )  # (no +1 ) since the server deployment already runs one node
            ]
            services = [create_k3s_kubeapi_service(namespace, cluster_config)]
        else:
            raise RuntimeError(
                f"Cannot create Beiboot wit provider {provider}: not supported."
            )

        # check if beiboot exists, handle that case

        #
        # ports to service
        #
        additional_services = ports_to_services(ports, namespace, cluster_config)
        if additional_services:
            services.extend(additional_services)
        #
        # Gefyra Nodeport
        #
        if hasattr(cluster_config, "gefyra") and cluster_config.gefyra.get("enabled"):
            try:
                gefyra_ports = cluster_config.gefyra.get("ports")
                lower_bound = int(gefyra_ports.split("-")[0])
                upper_bound = int(gefyra_ports.split("-")[1])
            except (IndexError, AttributeError, ValueError) as e:
                logger.error(f"Cannot read Gefyra configuration due to: {e}")
            else:
                taken_ports = get_taken_gefyra_ports(custom_api, configuration)
                try:
                    gefyra_nodeport = random.choice(
                        [
                            port
                            for port in range(lower_bound, upper_bound + 1)
                            if port not in taken_ports
                        ]
                    )
                    logger.info(f"Requesting Gefyra Nodeport: {gefyra_nodeport}")
                    services.append(
                        gefyra_service(gefyra_nodeport, namespace, cluster_config)
                    )
                    _ips = get_external_node_ips(core_v1_api, configuration)
                    gefyra_endpoint = _ips[0] if _ips else None
                except IndexError:
                    logger.error(
                        f"No free Gefyra port available for this cluster. "
                        f"lower bound: {lower_bound}, upper bound: {upper_bound}, "
                        f"taken ports: {len(taken_ports)}"
                    )

        #
        # Create the workloads
        #
        workloads = server_workloads + node_workloads
        for sts in workloads:
            logger.debug("Creating: " + str(sts))
            handle_create_statefulset(logger, sts, namespace)

        #
        # Create the services
        #
        for svc in services:
            logger.debug("Creating: " + str(svc))
            handle_create_service(logger, svc, namespace)
    except Exception as e:  # noqa
        logger.error(traceback.format_exc())
        logger.error("Could not create cluster due to the following error: " + str(e))
        custom_api.patch_namespaced_custom_object(
            namespace=configuration.NAMESPACE,
            name=body.metadata.name,
            body={"beibootNamespace": namespace},
            group="getdeck.dev",
            plural="beiboots",
            version="v1",
        )
    else:
        #
        # schedule startup tasks, work on them async
        #
        loop = asyncio.get_event_loop_policy().get_event_loop()
        aw_api_server_ready = loop.create_task(
            check_workload_ready(server_workloads[0], cluster_config)
        )

        if hasattr(cluster_config, "gefyra") and cluster_config.gefyra.get("enabled"):
            cluster_ready = loop.create_task(
                get_kubeconfig(
                    aw_api_server_ready,
                    server_workloads[0],
                    cluster_config,
                    gefyra_endpoint,
                    gefyra_nodeport,
                )
            )
            kubeconfig = await cluster_ready

            body_patch = {
                "beibootNamespace": namespace,
                "kubeconfig": kubeconfig,
                "gefyra": {"port": gefyra_nodeport, "endpoint": gefyra_endpoint},
            }
        else:
            cluster_ready = loop.create_task(
                get_kubeconfig(aw_api_server_ready, server_workloads[0], cluster_config)
            )
            kubeconfig = await cluster_ready
            body_patch = {"beibootNamespace": namespace, "kubeconfig": kubeconfig}

        custom_api.patch_namespaced_custom_object(
            namespace=configuration.NAMESPACE,
            name=body.metadata.name,
            body=body_patch,
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
    if namespace:
        handle_delete_namespace(logger, namespace)

    kopf.info(
        body,
        reason="Removed",
        message=f"The Beiboot {body['metadata']['name']} has been removed",
    )
