from typing import Optional

import kubernetes as k8s


app_v1_api = k8s.client.AppsV1Api()
core_v1_api = k8s.client.CoreV1Api()


def handle_create_statefulset(
    logger, statefulset: k8s.client.V1StatefulSet, namespace: str
) -> None:
    try:
        app_v1_api.create_namespaced_stateful_set(body=statefulset, namespace=namespace)
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


def handle_delete_statefulset(logger, name: str, namespace: str) -> None:
    try:
        app_v1_api.delete_namespaced_stateful_set(name=name, namespace=namespace)
    except k8s.client.exceptions.ApiException as e:
        if e.status == 404:
            pass
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
    except k8s.client.exceptions.ApiException as e:
        if e.status in [409, 422]:
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


def handle_delete_service(logger, name: str, namespace: str) -> None:
    try:
        core_v1_api.delete_namespaced_service(name=name, namespace=namespace)
    except k8s.client.exceptions.ApiException as e:
        if e.status == 404:
            pass
        else:
            raise e


def handle_create_namespace(logger, namespace: str) -> str:
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


async def handle_delete_namespace(logger, namespace) -> Optional[k8s.client.V1Status]:
    try:
        status = core_v1_api.delete_namespace(namespace)
        logger.info(f"Deleted namespace for beiboot: {namespace}")
        return status
    except k8s.client.exceptions.ApiException:
        pass
