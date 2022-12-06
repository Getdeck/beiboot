import logging
import shutil
import subprocess
from time import sleep

import pytest
from kopf.testing import KopfRunner

CLUSTER_NAME = "beiboot-test-cluster"


def pytest_addoption(parser):
    parser.addoption("--k8s-version", action="store")
    parser.addoption("--cluster-timeout", action="store")
    parser.addini("cluster_timeout", "The timeout waiting for Beiboot states")


@pytest.fixture(scope="package")
def kubeconfig(request):
    if shutil.which("minikube") is None:
        raise RuntimeError("You need 'minikube' installed to run these tests.")

    k8s_version = request.config.option.k8s_version
    if k8s_version is None:
        k8s_version = "v1.24.3"

    logging.getLogger().info("Setting up Minikube")

    ps = subprocess.run(
        f"minikube start -p {CLUSTER_NAME} --cpus=max --memory=4000 --driver=docker --kubernetes-version={k8s_version} "
        "--addons=default-storageclass storage-provisioner",
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

    def teardown():
        logging.getLogger().info("Removing Minikube")
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
    import kubernetes as k8s

    for _i in range(0, 10):
        try:
            k8s.config.load_kube_config()
            core_api = k8s.client.CoreV1Api()
            core_api.list_namespace()
            break
        except Exception:  # noqa
            sleep(1)
            continue
    else:
        raise RuntimeError("There was an error setting up Minikube correctly")
    return None


@pytest.fixture(scope="session")
def kubectl(request):
    def _fn(arguments: list[str]):
        _cmd = "minikube kubectl -- " + " ".join(arguments)
        logging.getLogger().debug(f"Running: {_cmd}")
        ps = subprocess.run(_cmd, shell=True, stdout=subprocess.PIPE)
        return ps.stdout.decode()

    return _fn


def _ensure_namespace(kubectl):
    output = kubectl(["get", "ns"])
    if "getdeck" in output:
        return
    else:
        kubectl(["create", "ns", "getdeck"])


@pytest.fixture(scope="module")
def operator(request, kubeconfig, kubectl):

    _ensure_namespace(kubectl)
    operator = KopfRunner(["run", "-A", "--dev", "main.py"])
    operator.__enter__()

    kopf_logger = logging.getLogger("kopf")
    kopf_logger.setLevel(logging.CRITICAL)
    beiboot_logger = logging.getLogger("beiboot")
    beiboot_logger.setLevel(logging.CRITICAL)

    def teardown():
        beiboots = kubectl(["-n", "getdeck", "get", "bbt"])
        for beiboot in beiboots.split("\n"):
            bbt_name = beiboot.split(" ")[0]
            kubectl(["-n", "getdeck", "delete", "bbt", bbt_name])
            sleep(5)
        operator.__exit__(None, None, None)
        assert operator.exit_code == 0
        assert operator.exception is None

    request.addfinalizer(teardown)
    return operator


@pytest.fixture(scope="session")
def timeout(request) -> int:
    cluster_timeout = request.config.option.cluster_timeout or request.config.getini(
        "cluster_timeout"
    )
    if cluster_timeout is None:
        return 60
    else:
        return int(cluster_timeout)
