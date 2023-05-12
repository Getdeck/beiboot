import logging
import os
import shutil
import subprocess
import sys
from time import sleep

import pytest

CLUSTER_NAME = "beiboot-test-cluster"


def pytest_addoption(parser):
    parser.addoption("--k8s-version", action="store")
    parser.addoption("--cluster-timeout", action="store")
    parser.addini("cluster_timeout", "The timeout waiting for Beiboot states")


@pytest.fixture(scope="session")
def kubectl(request):
    def _fn(arguments: list[str]):
        _cmd = "minikube kubectl -- " + " ".join(arguments)
        logging.getLogger().debug(f"Running: {_cmd}")
        ps = subprocess.run(_cmd, shell=True, stdout=subprocess.PIPE)
        return ps.stdout.decode(sys.stdout.encoding)

    return _fn


@pytest.fixture(scope="module")
def minikube(request, kubectl):
    logger = logging.getLogger()
    if shutil.which("minikube") is None:
        raise RuntimeError("You need 'minikube' installed to run these tests.")

    k8s_version = request.config.option.k8s_version
    if k8s_version is None:
        k8s_version = "v1.24.3"

    logger.info("Setting up Minikube")

    ps = subprocess.run(
        f"minikube start -p {CLUSTER_NAME} --cpus=max --memory=4000 --driver=docker "
        f"--kubernetes-version={k8s_version}",
        shell=True,
        stdout=subprocess.DEVNULL,
    )
    assert ps.returncode == 0
    subprocess.run(
        f"minikube profile {CLUSTER_NAME}",
        shell=True,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    # enable/disable addons for volume snapshot capabilities
    subprocess.run(
        "minikube addons enable volumesnapshots",
        shell=True,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    subprocess.run(
        "minikube addons enable csi-hostpath-driver",
        shell=True,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    subprocess.run(
        "minikube addons disable default-storageclass",
        shell=True,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    subprocess.run(
        "minikube addons disable storage-provisioner",
        shell=True,
        check=True,
        stdout=subprocess.DEVNULL,
    )

    import kubernetes as k8s

    # patch storage class from csi-hostpath-driver to make it default
    k8s.config.load_kube_config()
    storage_api = k8s.client.StorageV1Api()
    body = {"metadata": {"annotations": {"storageclass.kubernetes.io/is-default-class": "true"}}}
    storage_api.patch_storage_class(name="csi-hostpath-sc", body=body)

    for _i in range(0, 10):
        try:
            core_api = k8s.client.CoreV1Api()
            core_api.list_namespace()
            break
        except Exception:  # noqa
            sleep(1)
            continue
    else:
        raise RuntimeError("There was an error setting up Minikube correctly")

    def teardown():
        logger.info("Removing Minikube")
        subprocess.run(
            f"minikube delete -p {CLUSTER_NAME}",
            shell=True,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        subprocess.run(
            "minikube profile default",
            shell=True,
            check=True,
            stdout=subprocess.DEVNULL,
        )

    request.addfinalizer(teardown)
    return CLUSTER_NAME


def _ensure_namespace(kubectl):
    output = kubectl(["get", "ns"])
    if "getdeck" in output:
        return
    else:
        kubectl(["create", "ns", "getdeck"])


@pytest.fixture(scope="module")
def crds(request, minikube, kubectl):
    import kubernetes as k8s

    extension_api = k8s.client.ApiextensionsV1Api()
    logger = logging.getLogger()
    _ensure_namespace(kubectl)

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
            extension_api.delete_custom_resource_definition(name=shelf_def.metadata.name)
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
def minikube_ip(request, minikube):
    ip = subprocess.check_output(["minikube", "-p", CLUSTER_NAME, "ip"])
    return ip.decode(sys.stdout.encoding).strip()


@pytest.fixture(scope="module")
def operator(request, minikube, kubectl):
    logger = logging.getLogger()
    _ensure_namespace(kubectl)

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

    def teardown():
        import kubernetes as k8s

        extension_api = k8s.client.ApiextensionsV1Api()

        beiboots = kubectl(["-n", "getdeck", "get", "bbt"])
        for beiboot in beiboots.split("\n"):
            bbt_name = beiboot.split(" ")[0]
            kubectl(["-n", "getdeck", "delete", "bbt", bbt_name])
            sleep(5)
        shelves = kubectl(["-n", "getdeck", "get", "shelf"])
        for shelf in shelves.split("\n"):
            shelf_name = shelf.split(" ")[0]
            kubectl(["-n", "getdeck", "delete", "shelf", shelf_name])
            sleep(5)
        logger.info("Stopping the Operator")
        operator.terminate()
        operator.kill()
        try:
            extension_api.delete_custom_resource_definition(name="beiboots.getdeck.dev")
            logger.info("Beiboot CRD deleted")
        except k8s.client.exceptions.ApiException:
            pass
        try:
            extension_api.delete_custom_resource_definition(name="shelves.beiboots.getdeck.dev")
            logger.info("Shelf CRD deleted")
        except k8s.client.exceptions.ApiException:
            pass

    request.addfinalizer(teardown)
    return None


@pytest.fixture(scope="session")
def timeout(request):
    cluster_timeout = request.config.option.cluster_timeout or request.config.getini(
        "cluster_timeout"
    )
    if not bool(cluster_timeout):
        return 60
    else:
        return int(cluster_timeout)
