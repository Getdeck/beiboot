from typing import Optional

import kubernetes as k8s


app_v1_api = k8s.client.AppsV1Api()
core_v1_api = k8s.client.CoreV1Api()
rbac_v1_api = k8s.client.RbacAuthorizationV1Api()


def handle_create_statefulset(
    logger, statefulset: k8s.client.V1StatefulSet, namespace: str
) -> None:
    """
    It creates a statefulset if it doesn't exist, and patches it if it does

    :param logger: a logger object
    :param statefulset: The statefulset object that we want to create
    :type statefulset: k8s.client.V1StatefulSet
    :param namespace: The namespace in which the statefulset will be created
    :type namespace: str
    """
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
    """
    It deletes a statefulset

    :param logger: a logger object
    :param name: The name of the statefulset
    :type name: str
    :param namespace: The namespace where the statefulset is located
    :type namespace: str
    """
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
    """
    If the service already exists, patch it with the current configuration

    :param logger: a logger object
    :param service: The service object to create
    :type service: k8s.client.V1Service
    :param namespace: The namespace in which the service should be created
    :type namespace: str
    """
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
    """
    It deletes a service in a namespace

    :param logger: a logger object
    :param name: The name of the service to delete
    :type name: str
    :param namespace: The namespace in which the service is to be created
    :type namespace: str
    """
    try:
        core_v1_api.delete_namespaced_service(name=name, namespace=namespace)
    except k8s.client.exceptions.ApiException as e:
        if e.status == 404:
            pass
        else:
            raise e


def handle_create_namespace(logger, namespace: str) -> str:
    """
    It creates a namespace in Kubernetes

    :param logger: a logger object
    :param namespace: The namespace to create
    :type namespace: str
    :return: The namespace that was created.
    """
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
    """
    It deletes a namespace

    :param logger: a logger object
    :param namespace: The namespace to delete
    :return: The status of the delete operation.
    """
    try:
        status = core_v1_api.delete_namespace(namespace)
        logger.info(f"Deleted namespace for beiboot: {namespace}")
        return status
    except k8s.client.exceptions.ApiException:
        pass
