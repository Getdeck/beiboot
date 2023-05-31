import logging
import os
import subprocess
import sys
from time import sleep

import pytest
from pytest_kubernetes.options import ClusterOptions
from pytest_kubernetes.providers import AClusterManager, select_provider_manager

CLUSTER_NAME = "beiboot-test-cluster"


def pytest_addoption(parser):
    parser.addoption("--cluster-timeout", action="store")
    parser.addini("cluster_timeout", "The timeout waiting for Beiboot states")


@pytest.fixture(scope="module")
def minikube(request):
    logger = logging.getLogger()
    logger.info("Setting up Minikube")
    k8s: AClusterManager = select_provider_manager("minikube")(CLUSTER_NAME)

    k8s_version = _k8s_version(request)

    # ClusterOptions without kubeconfig_path forces pytest-kubernetes to always write a new kubeconfig file to disk
    k8s.create(
        ClusterOptions(api_version=k8s_version, cluster_timeout=_timeout(request)),
        options=[
            "--cpus",
            "max",
            "--memory",
            "4000",
        ],
    )

    os.environ["KUBECONFIG"] = str(k8s.kubeconfig)
    print(f"This test run's kubeconfig location: {k8s.kubeconfig}")

    import kubernetes

    kubernetes.config.load_kube_config(config_file=str(k8s.kubeconfig))

    # enable/disable addons for volume snapshot capabilities
    k8s._exec(["addons", "-p", k8s.cluster_name, "enable", "volumesnapshots"])
    k8s._exec(["addons", "-p", k8s.cluster_name, "enable", "csi-hostpath-driver"])
    k8s._exec(["addons", "-p", k8s.cluster_name, "disable", "default-storageclass"])
    k8s._exec(["addons", "-p", k8s.cluster_name, "disable", "storage-provisioner"])

    # patch storage class from csi-hostpath-driver to make it default
    storage_api = kubernetes.client.StorageV1Api()
    body = {
        "metadata": {
            "annotations": {"storageclass.kubernetes.io/is-default-class": "true"}
        }
    }
    storage_api.patch_storage_class(name="csi-hostpath-sc", body=body)

    # TODO: can we ensure that we are really connected to the correct cluster?
    for _i in range(0, 10):
        try:
            core_api = kubernetes.client.CoreV1Api()
            core_api.list_namespace()
            break
        except Exception:  # noqa
            sleep(1)
            continue
    else:
        raise RuntimeError("There was an error setting up Minikube correctly")

    yield k8s
    k8s.delete()


def _ensure_namespace(kubectl):
    output = kubectl(["get", "ns"])
    if "getdeck" in output:
        return
    else:
        kubectl(["create", "ns", "getdeck"])


@pytest.fixture(scope="module")
def crds(request, minikube):
    import kubernetes as k8s

    extension_api = k8s.client.ApiextensionsV1Api()
    logger = logging.getLogger()
    _ensure_namespace(minikube.kubectl)

    module_path = os.path.join("..", "operator", "beiboot", "resources", "crds.py")
    with open(module_path, "r") as f:
        data = f.read()
    # imports create_func for _crd(...), i.e. create_beiboot_definition(namespace: str) and
    # create_shelf_definition(namespace: str))
    exec(data, globals())

    def _crd(create_func_name, crd_name):
        create_func = globals()[create_func_name]
        crd_def = create_func("default")  # noqa
        try:
            extension_api.create_custom_resource_definition(body=crd_def)
            logger.info(f"{crd_name} CRD created")
        except k8s.client.exceptions.ApiException as e:
            if e.status == 409:
                logger.warning(f"{crd_name} CRD already available")
            else:
                raise e
        return crd_def

    bbt_def = _crd("create_beiboot_definition", "Beiboot")
    shelf_def = _crd("create_shelf_definition", "Shelf")

    def remove_extensions():
        try:
            extension_api.delete_custom_resource_definition(name=bbt_def.metadata.name)
            logger.info("Beiboot CRD deleted")
        except k8s.client.exceptions.ApiException:
            pass
        try:
            extension_api.delete_custom_resource_definition(
                name=shelf_def.metadata.name
            )
            logger.info("Shelf CRD deleted")
        except k8s.client.exceptions.ApiException:
            pass
        sleep(5)

    request.addfinalizer(remove_extensions)


@pytest.fixture(scope="session")
def local_kubectl(request):
    def _fn(arguments: list[str], kubeconfig_path: str):
        _cmd = f"kubectl --kubeconfig {kubeconfig_path} " + " ".join(arguments)
        logging.getLogger().debug(f"Running: {_cmd}")
        ps = subprocess.run(_cmd, shell=True, stdout=subprocess.PIPE)
        return ps.stdout.decode(sys.stdout.encoding)

    return _fn


@pytest.fixture
def minikube_ip(request, minikube: AClusterManager):
    ip = subprocess.check_output(["minikube", "-p", minikube.cluster_name, "ip"])
    return ip.decode(sys.stdout.encoding).strip()


@pytest.fixture(scope="session")
def default_k3s_image():
    name = "rancher/k3s:v1.24.3-k3s1"
    subprocess.run(
        f"docker pull {name}", shell=True,
    )
    return name


@pytest.fixture(scope="module")
def operator(minikube, default_k3s_image):
    logger = logging.getLogger()
    _ensure_namespace(minikube.kubectl)

    # do not actually pull k3s images
    os.environ["K3S_IMAGE_PULLPOLICY"] = "Never"
    minikube.load_image(default_k3s_image)
    logger.info("Starting the Operator")
    # start the operator
    operator = subprocess.Popen(
        ["poetry", "run", "kopf", "run", "-A", "--dev", "main.py"],
        cwd=os.path.join("..", "operator"),
        bufsize=1,
        universal_newlines=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    sleep(7)
    if operator.poll() is None:
        logger.info("Operator is running")
    else:
        raise RuntimeError("There was an error starting the Operator")

    yield minikube

    import kubernetes as k8s

    extension_api = k8s.client.ApiextensionsV1Api()

    try:
        beiboots = minikube.kubectl(["-n", "getdeck", "get", "bbt"])
        for beiboot in beiboots.get("items"):
            minikube.kubectl(["-n", "getdeck", "delete", "bbt", beiboot["metadata"]["name"]])
            sleep(1)
    except RuntimeError:
        # case:
        # RuntimeError: error: the server doesn't have a resource type "bbt"
        pass
    try:
        shelves = minikube.kubectl(["-n", "getdeck", "get", "shelf"])
        for shelf in shelves.get("items"):
            minikube.kubectl(["-n", "getdeck", "delete", "shelf", shelf["metadata"]["name"]])
            sleep(1)
    except RuntimeError:
        # case:
        # RuntimeError: error: the server doesn't have a resource type "shelf"
        pass
    logger.info("Stopping the Operator")
    operator.terminate()
    operator.kill()
    try:
        extension_api.delete_custom_resource_definition(name="beiboots.getdeck.dev")
        logger.info("Beiboot CRD deleted")
    except k8s.client.exceptions.ApiException:
        pass
    try:
        extension_api.delete_custom_resource_definition(
            name="shelves.beiboots.getdeck.dev"
        )
        logger.info("Shelf CRD deleted")
    except k8s.client.exceptions.ApiException:
        pass


def _k8s_version(request) -> str:
    k8s_version = request.config.option.k8s_version
    if not k8s_version:
        k8s_version = "1.24.3"
    return k8s_version


def _timeout(request) -> int:
    cluster_timeout = request.config.option.cluster_timeout or request.config.getini("cluster_timeout")
    if not cluster_timeout:
        return 60
    else:
        return int(cluster_timeout)


@pytest.fixture(scope="session")
def timeout(request):
    return _timeout(request)
