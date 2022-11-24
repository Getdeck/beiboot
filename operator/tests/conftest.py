import logging
import shutil
import subprocess
import pytest

CLUSTER_NAME = "beiboot-test-cluster"


def pytest_addoption(parser):
    parser.addoption("--k8s-version", action="store")
    parser.addoption("--cluster-timeout", action="store")


@pytest.fixture(scope="class")
def kubeconfig(request):
    if shutil.which("minikube") is None:
        raise RuntimeError("You need 'minikube' installed to run these tests.")

    k8s_version = request.config.option.k8s_version
    if k8s_version is None:
        k8s_version = "v1.24.3"

    logging.getLogger().info("Setting up Minikube")
    ps = subprocess.run(
        f"minikube start -p {CLUSTER_NAME} --driver=docker --kubernetes-version={k8s_version}",
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

    k8s.config.load_kube_config()
    return None


@pytest.fixture(scope="session")
def kubectl(request):
    def _fn(arguments: list[str]):
        _cmd = "minikube kubectl -- " + " ".join(arguments)
        logging.getLogger().debug(f"Running: {_cmd}")
        ps = subprocess.run(_cmd, shell=True, stdout=subprocess.PIPE)
        return ps.stdout.decode()

    return _fn


@pytest.fixture(scope="session")
def timeout(request) -> int:
    cluster_timeout = request.config.option.cluster_timeout
    if cluster_timeout is None:
        return 120
    else:
        return int(cluster_timeout)
