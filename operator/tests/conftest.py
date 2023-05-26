import logging
import os
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


# @pytest.fixture(scope="package")
# def kubeconfig(request):
#     if shutil.which("minikube") is None:
#         raise RuntimeError("You need 'minikube' installed to run these tests.")
#
#     k8s_version = request.config.option.k8s_version
#     if k8s_version is None:
#         k8s_version = "v1.24.3"
#
#     logging.getLogger().info("Setting up Minikube")
#
#     ps = subprocess.run(
#         f"minikube start -p {CLUSTER_NAME} --cpus=max --memory=4000 --driver=docker "
#         f"--kubernetes-version={k8s_version}",
#         shell=True,
#         stdout=subprocess.DEVNULL,
#     )
#     assert ps.returncode == 0
#     subprocess.run(
#         f"minikube profile {CLUSTER_NAME}",
#         shell=True,
#         check=True,
#         stdout=subprocess.DEVNULL,
#     )
#     # enable/disable addons for volume snapshot capabilities
#     subprocess.run(
#         "minikube addons enable volumesnapshots",
#         shell=True,
#         check=True,
#         stdout=subprocess.DEVNULL,
#     )
#     subprocess.run(
#         "minikube addons enable csi-hostpath-driver",
#         shell=True,
#         check=True,
#         stdout=subprocess.DEVNULL,
#     )
#     subprocess.run(
#         "minikube addons disable default-storageclass",
#         shell=True,
#         check=True,
#         stdout=subprocess.DEVNULL,
#     )
#     subprocess.run(
#         "minikube addons disable storage-provisioner",
#         shell=True,
#         check=True,
#         stdout=subprocess.DEVNULL,
#     )
#
#     def teardown():
#         logging.getLogger().info("Removing Minikube")
#         subprocess.run(
#             f"minikube delete -p {CLUSTER_NAME}",
#             shell=True,
#             check=True,
#             stdout=subprocess.DEVNULL,
#         )
#         subprocess.run(
#             "minikube profile default",
#             shell=True,
#             check=True,
#             stdout=subprocess.DEVNULL,
#         )
#
#     request.addfinalizer(teardown)
#     import kubernetes as k8s
#
#     # patch storage class from csi-hostpath-driver to make it default
#     k8s.config.load_kube_config()
#     storage_api = k8s.client.StorageV1Api()
#     body = {
#         "metadata": {
#             "annotations": {"storageclass.kubernetes.io/is-default-class": "true"}
#         }
#     }
#     storage_api.patch_storage_class(name="csi-hostpath-sc", body=body)
#
#     for _i in range(0, 10):
#         try:
#             core_api = k8s.client.CoreV1Api()
#             core_api.list_namespace()
#             break
#         except Exception:  # noqa
#             sleep(1)
#             continue
#     else:
#         raise RuntimeError("There was an error setting up Minikube correctly")
#     return None
#
#
# @pytest.fixture(scope="session")
@pytest.fixture(scope="module")
def kubectl(request, minikube):
    # def _fn(arguments: list[str]):
    #     _cmd = "minikube kubectl -- " + " ".join(arguments)
    #     logging.getLogger().debug(f"Running: {_cmd}")
    #     ps = subprocess.run(_cmd, shell=True, stdout=subprocess.PIPE)
    #     return ps.stdout.decode()
    #
    # return _fn
    return minikube.kubectl


def _ensure_namespace(kubectl):
    output = kubectl(["get", "ns"])
    if "getdeck" in output:
        return
    else:
        kubectl(["create", "ns", "getdeck"])


@pytest.fixture(scope="module")
def operator(request, minikube):
    from kopf.testing import KopfRunner

    print(f"KUBECONFIG: {os.environ.get('KUBECONFIG')}")

    _ensure_namespace(minikube.kubectl)
    operator = KopfRunner(["run", "-A", "--dev", "main.py"])
    operator.__enter__()

    kopf_logger = logging.getLogger("kopf")
    kopf_logger.setLevel(logging.CRITICAL)
    beiboot_logger = logging.getLogger("beiboot")
    beiboot_logger.setLevel(logging.CRITICAL)

    yield minikube

    try:
        beiboots = minikube.kubectl(["-n", "getdeck", "get", "bbt"])
        for beiboot in beiboots.split("\n"):
            bbt_name = beiboot.split(" ")[0]
            minikube.kubectl(["-n", "getdeck", "delete", "bbt", bbt_name])
            sleep(5)
    except RuntimeError:
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
        return 60
    else:
        return int(cluster_timeout)


@pytest.fixture(scope="session")
def timeout(request) -> int:
    return _timeout(request)


@pytest.fixture(scope="session")
def core_api(minikube):
    import kubernetes as k8s

    k8s.config.load_kube_config(config_file=str(minikube.kubeconfig))

    return k8s.client.CoreV1Api()
