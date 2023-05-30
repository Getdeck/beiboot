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


@pytest.fixture(autouse=True, scope="module")
def reload_kubernetes():
    for key in list(sys.modules.keys()):
        if (
            key.startswith("kubernetes")
            or key.startswith("k8s")
            or key.startswith("beiboot")
        ):
            del sys.modules[key]


@pytest.fixture(scope="module")
def minikube(request):
    k8s: AClusterManager = select_provider_manager("minikube")(CLUSTER_NAME)
    # ClusterOptions without kubeconfig_path forces pytest-kubernetes to always write a new kubeconfig file to disk
    k8s.create(
        ClusterOptions(api_version=_k8s_version(request), cluster_timeout=_timeout(request)),
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


@pytest.fixture(scope="session")
def default_k3s_image():
    name = "rancher/k3s:v1.24.3-k3s1"
    subprocess.run(
        f"docker pull {name}", shell=True,
    )
    return name


@pytest.fixture(scope="module")
def operator(minikube, default_k3s_image):
    from kopf.testing import KopfRunner

    # do not actually pull k3s images
    os.environ["K3S_IMAGE_PULLPOLICY"] = "Never"
    minikube.load_image(default_k3s_image)
    _ensure_namespace(minikube.kubectl)
    operator = KopfRunner(["run", "-A", "--dev", "main.py"])
    operator.__enter__()

    kopf_logger = logging.getLogger("kopf")
    # kopf_logger.setLevel(logging.INFO)
    kopf_logger.setLevel(logging.CRITICAL)
    beiboot_logger = logging.getLogger("beiboot")
    # beiboot_logger.setLevel(logging.INFO)
    beiboot_logger.setLevel(logging.CRITICAL)
    minikube.wait(
        "crd/beiboots.getdeck.dev",
        "condition=established",
        timeout=30
    )

    yield minikube

    try:
        beiboots = minikube.kubectl(["-n", "getdeck", "get", "bbt"])
        for beiboot in beiboots["items"]:
            minikube.kubectl(["-n", "getdeck", "delete", "bbt", beiboot["metadata"]["name"]])
            sleep(1)
    except Exception:
        # case:
        # RuntimeError: error: the server doesn't have a resource type "bbt"
        pass
    operator.__exit__(None, None, None)
    assert operator.exit_code == 0
    assert operator.exception is None


def _k8s_version(request) -> str:
    k8s_version = request.config.option.k8s_version
    if not k8s_version:
        k8s_version = "1.24.3"
    return k8s_version


def _timeout(request) -> int:
    cluster_timeout = request.config.option.cluster_timeout or request.config.getini("cluster_timeout")
    if not cluster_timeout:
        return 120
    else:
        return int(cluster_timeout)


@pytest.fixture(scope="session")
def timeout(request) -> int:
    return _timeout(request)
