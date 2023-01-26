from typing import Optional

import kopf
import kubernetes as k8s

app_v1_api = k8s.client.AppsV1Api()
core_v1_api = k8s.client.CoreV1Api()
rbac_v1_api = k8s.client.RbacAuthorizationV1Api()
custom_api = k8s.client.CustomObjectsApi()


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
            logger.warning(
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
                # TODO label these namespaces so we can safely remove then in case of uninstall
            )
        )
        logger.info(f"Created namespace for beiboot: {namespace}")
    except k8s.client.exceptions.ApiException as e:
        if e.status in [409, 422]:
            logger.warning(f"Namespace for beiboot {namespace} already exists")
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
        return None


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
                    ),
                    k8s.client.V1PolicyRule(
                        api_groups=[""],
                        resources=["configmaps"],
                        verbs=["get", "patch"],
                    ),
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
    token_secret_name = f"{name}-token"
    try:
        token_secret = core_v1_api.read_namespaced_secret(
            name=token_secret_name, namespace=namespace
        )
        data = token_secret.data
    except k8s.client.exceptions.ApiException as e:
        if e.status == 404:
            try:
                token_secret = core_v1_api.create_namespaced_secret(
                    namespace=namespace,
                    body=k8s.client.V1Secret(
                        metadata=k8s.client.V1ObjectMeta(
                            name=token_secret_name,
                            namespace=namespace,
                            annotations={"kubernetes.io/service-account.name": name},
                        ),
                        type="kubernetes.io/service-account-token",
                    ),
                )
                data = token_secret.data
            except k8s.client.exceptions.ApiException as e:
                raise kopf.PermanentError(str(e))
        else:
            raise kopf.PermanentError(str(e))  # type: ignore
    if data is None:
        raise kopf.TemporaryError("Serviceaccount token not yet generated", delay=1)
    return data


def create_volume_snapshot_from_pvc_resource(
        name: str,
        namespace: str,
        volume_snapshot_class: str,
        pvc_name: str
) -> dict:
    """
    Return VolumeSnapshot for PVC K8s resource as dict.

    :param name: The name of the VolumeSnapshot that is to be created
    :param namespace: The namespace that the PVC is located in and in that the VolumeSnapshot is to be created
    :param volume_snapshot_class: The VolumeSnapshotClass to use for the VolumeSnapshotContent
    :param pvc_name: The name of the PersistentVolumeClaim for which the VolumeSnapshot is to be created
    """
    return {
        "apiVersion": "snapshot.storage.k8s.io/v1",
        "kind": "VolumeSnapshot",
        "metadata": {
            "name": f"{name}",
            "namespace": f"{namespace}",
        },
        "spec": {
            "volumeSnapshotClassName": f"{volume_snapshot_class}",
            "source": {
                "persistentVolumeClaimName": f"{pvc_name}"
            }
        }
    }


def create_volume_snapshot_pre_provisioned_resource(name: str, namespace: str, volume_snapshot_content: str) -> dict:
    """
    Return pre-provisioned VolumeSnapshot K8s resource as dict.

    :param name: The name of the VolumeSnapshot that is to be created
    :param namespace: The namespace that the PVC is located in and in that the VolumeSnapshot is to be created
    :param volume_snapshot_content: The associated pre-provisioned VolumeSnapshotContent
    """
    return {
        "apiVersion": "snapshot.storage.k8s.io/v1",
        "kind": "VolumeSnapshot",
        "metadata": {
            "name": f"{name}",
            "namespace": f"{namespace}",
        },
        "spec": {
            "source": {
                "volumeSnapshotContentName": f"{volume_snapshot_content}",
            },
        }
    }


def handle_create_volume_snapshot(logger, body: dict):
    """
    :param logger: a logger object
    :param body: The dict that describes the K8s resource
    """
    try:
        # FIXME: python-kubernetes doesn't support VolumeSnapshots; if it does support them one day, we can change it 
        #  here
        namespace = body.get('metadata').get('namespace')
        k8s.client.CustomObjectsApi().create_namespaced_custom_object(
            group="snapshot.storage.k8s.io",
            version="v1",
            namespace=f"{namespace}",
            plural="volumesnapshots",
            body=body,
        )
        logger.info(
            f"Created VolumeSnapshot {body.get('metadata').get('name')} in namespace {namespace}."
        )
    except k8s.client.exceptions.ApiException as e:
        raise e


async def handle_delete_volume_snapshot(logger, name: str, namespace: str) -> Optional[k8s.client.V1Status]:
    try:
        # FIXME: python-kubernetes doesn't support VolumeSnapshots; if it does support them one day, we can change it 
        #  here
        status = k8s.client.CustomObjectsApi().delete_namespaced_custom_object(
            group="snapshot.storage.k8s.io",
            version="v1",
            namespace=f"{namespace}",
            plural="volumesnapshots",
            name=name,
        )
        logger.info(f"Deleted VolumeSnapshot {name} in namespace {namespace}")
        return status
    except k8s.client.exceptions.ApiException:
        return None


def create_volume_snapshot_content_pre_provisioned_resource(
        name: str,
        driver: str,
        snapshot_handle: str,
        volume_snapshot_ref_name: str,
        volume_snapshot_ref_namespace: str,
        deletion_policy: str = "Delete",
        source_volume_mode: str = "Filesystem",
) -> dict:
    """
    Return pre-provisioned VolumeSnapshot K8s resource as dict.

    :param name: The name of the VolumeSnapshot that is to be created
    :param driver: CSI Driver Name (e.g. see https://kubernetes-csi.github.io/docs/drivers.html)
    :param snapshot_handle: The snapshot handle of the CSI-driver, where the content is located at
    :param volume_snapshot_ref_name: The name of the pre-provisioned VolumeSnapshot that the VolumeSnapshotContent will
        be associated with
    :param volume_snapshot_ref_namespace: The namespace of the pre-provisioned VolumeSnapshot that the
        VolumeSnapshotContent will be associated with
    :param deletion_policy: deletionPolicy of the VolumeSnapshotContent, either "Delete" or "Retain"
    :param source_volume_mode: sourceVolumeMode of the VolumeSnapshotContent, either "Filesystem" or "Block"
    """
    return {
        "apiVersion": "snapshot.storage.k8s.io/v1",
        "kind": "VolumeSnapshotContent",
        "metadata": {
            "name": f"{name}",
        },
        "spec": {
            "deletionPolicy": f"{deletion_policy}",
            "driver": f"{driver}",
            "source": {
                "snapshotHandle": f"{snapshot_handle}",
            },
            "sourceVolumeMode": f"{source_volume_mode}",
            "volumeSnapshotRef": {
                "name": f"{volume_snapshot_ref_name}",
                "namespace": f"{volume_snapshot_ref_namespace}"
            }
        }
    }


def handle_create_volume_snapshot_content(logger, body: dict):
    """
    :param logger: a logger object
    :param body: The dict that describes the K8s resource
    """
    try:
        # FIXME: python-kubernetes doesn't support VolumeSnapshotContents; if it does support them one day, we can 
        #  change it here
        k8s.client.CustomObjectsApi().create_cluster_custom_object(
            group="snapshot.storage.k8s.io",
            version="v1",
            plural="volumesnapshotcontents",
            body=body,
        )
        logger.info(
            f"VolumeSnapshotContent {body.get('metadata').get('name')} created."
        )
    except k8s.client.exceptions.ApiException as e:
        raise e


async def handle_delete_volume_snapshot_content(logger, name: str) -> Optional[k8s.client.V1Status]:
    try:
        # FIXME: python-kubernetes doesn't support VolumeSnapshotContents; if it does support them one day, we can 
        #  change it here
        status = k8s.client.CustomObjectsApi().delete_cluster_custom_object(
            group="snapshot.storage.k8s.io",
            version="v1",
            plural="volumesnapshotcontents",
            name=name,
        )
        logger.info(f"Deleted VolumeSnapshotContent {name}")
        return status
    except k8s.client.exceptions.ApiException:
        return None


async def create_volume_snapshots_from_shelf(logger, shelf: dict, cluster_namespace: str) -> dict:
    """
    Create pre-provisioned VolumeSnapshotContents and VolumeSnapshots from the data that is stored in the shelf.

    This assumes that the shelf is valid, i.e. volumeSnapshotContents are populated and state is ready.
    This assumes that the volumeSnapshotClass of the shelf exists.

    :param logger: logger instance
    :param shelf: shelf object as retrieved from K8s
    :param cluster_namespace: namespace of the beiboot cluster
    :return: mapping of node-name to name of the VolumeSnapshot
    """
    from beiboot.utils import get_volume_snapshot_class_by_name

    volume_snapshot_class = get_volume_snapshot_class_by_name(shelf["volumeSnapshotClass"], api_instance=custom_api)
    driver = volume_snapshot_class["driver"]
    mapping = {}
    for volume_snapshot_content in shelf["volumeSnapshotContents"]:
        node_name = volume_snapshot_content['node']
        volume_snapshot_content_name = f"{cluster_namespace}-{node_name}"
        volume_snapshot_name = volume_snapshot_content_name
        vsc_resource = create_volume_snapshot_content_pre_provisioned_resource(
            name=volume_snapshot_content_name,
            driver=driver,
            snapshot_handle=volume_snapshot_content["snapshotHandle"],
            volume_snapshot_ref_name=volume_snapshot_name,
            volume_snapshot_ref_namespace=cluster_namespace,
            deletion_policy="Delete"
        )
        handle_create_volume_snapshot_content(logger, body=vsc_resource)

        vs_resource = create_volume_snapshot_pre_provisioned_resource(
            name=volume_snapshot_name,
            namespace=cluster_namespace,
            volume_snapshot_content=volume_snapshot_content_name
        )
        handle_create_volume_snapshot(logger, body=vs_resource)

        mapping[node_name] = volume_snapshot_name

    return mapping
