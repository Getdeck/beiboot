from typing import Optional

import kopf
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


def handle_create_deployment(
    logger, deployment: k8s.client.V1Deployment, namespace: str
) -> None:
    try:
        app_v1_api.create_namespaced_deployment(body=deployment, namespace=namespace)
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
) -> k8s.client.V1Service:
    """
    If the service already exists, patch it with the current configuration

    :param logger: a logger object
    :param service: The service object to create
    :type service: k8s.client.V1Service
    :param namespace: The namespace in which the service should be created
    :type namespace: str
    :return: The service object
    """
    try:
        service = core_v1_api.create_namespaced_service(
            body=service, namespace=namespace
        )
    except k8s.client.exceptions.ApiException as e:
        if e.status in [409, 422]:
            logger.warn(
                f"Service {service.metadata.name} already available, now patching it with current configuration"
            )
            service = core_v1_api.patch_namespaced_service(
                name=service.metadata.name,
                body=service,
                namespace=namespace,
            )
            logger.info(f"Service {service.metadata.name} patched")
        else:
            raise e
    return service


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


def handle_create_beiboot_serviceaccount(logger, name: str, namespace: str) -> None:
    """
    It creates a service account, a role, and a role binding to allow the service account to port forward
    :param logger: a logger object
    :param name: The name of the service account to create
    :type name: str
    :param namespace: The namespace to create the service account in
    :type namespace: str
    """
    try:
        role = rbac_v1_api.create_namespaced_role(
            namespace=namespace,
            body=k8s.client.V1Role(
                metadata=k8s.client.V1ObjectMeta(
                    name="beiboot-allow-port-forward", namespace=namespace
                ),
                rules=[
                    k8s.client.V1PolicyRule(
                        api_groups=[""],
                        resources=["pods/portforward"],
                        verbs=["get", "list", "create"],
                    )
                ],
            ),
        )
        sa = core_v1_api.create_namespaced_service_account(
            namespace=namespace,
            body=k8s.client.V1ServiceAccount(
                metadata=k8s.client.V1ObjectMeta(name=name, namespace=namespace)
            ),
        )
        rbac_v1_api.create_namespaced_role_binding(
            namespace=namespace,
            body=k8s.client.V1RoleBinding(
                metadata=k8s.client.V1ObjectMeta(
                    name="beiboot-allow-port-forward", namespace=namespace
                ),
                subjects=[
                    k8s.client.V1Subject(kind="ServiceAccount", name=sa.metadata.name)
                ],
                role_ref=k8s.client.V1RoleRef(
                    kind="Role",
                    name=role.metadata.name,
                    api_group="rbac.authorization.k8s.io",
                ),
            ),
        )
        logger.info(f"Created serviceaccount and permissions for beiboot: {name}")
    except k8s.client.exceptions.ApiException as e:
        raise e


async def get_serviceaccount_data(name: str, namespace: str) -> dict[str, str]:
    try:
        sa = core_v1_api.read_namespaced_service_account(name=name, namespace=namespace)
        secrets = sa.secrets
        token_secret_name = secrets[0].name
        token_secret = core_v1_api.read_namespaced_secret(
            name=token_secret_name, namespace=namespace
        )
        return token_secret.data
    except k8s.client.exceptions.ApiException as e:
        raise kopf.TemporaryError(str(e))
