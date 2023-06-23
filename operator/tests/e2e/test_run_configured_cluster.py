from pathlib import Path

from pytest_kubernetes.providers import AClusterManager

from tests.utils import get_beiboot_data


BEIBOOT_NAME = "test-beiboot-configured"


def test_a_create_configured_beiboot(operator: AClusterManager, timeout):
    minikube = operator
    minikube.apply(Path("tests/fixtures/configured-beiboot.yaml"))
    # READY state
    minikube.wait(
        f"beiboots.getdeck.dev/{BEIBOOT_NAME}",
        "jsonpath=.state=READY",
        namespace="getdeck",
        timeout=120,
    )


def test_b_gefyra_disabled(minikube: AClusterManager):
    data = get_beiboot_data(BEIBOOT_NAME, minikube)
    assert data["parameters"]["gefyra"]["enabled"] is False
    assert data["gefyra"].get("endpoint") is None
    assert data["gefyra"].get("port") is None
    assert data["gefyra"] == {}


def test_c_parameters_set(minikube: AClusterManager):
    data = get_beiboot_data(BEIBOOT_NAME, minikube)
    assert data["parameters"]["nodes"] == 2
    assert data["parameters"]["ports"] == ["8080:80", "8443:443", "6443:6443"]
    assert data["parameters"]["k8sVersion"] == "1.24.3"
    image = minikube.kubectl(
        [
            "-n",
            f"getdeck-bbt-{BEIBOOT_NAME}",
            "get",
            "pod",
            "server-0",
            "-o",
            "jsonpath={.spec.containers[0].image}",
        ],
        as_dict=False,
    )
    assert image == "rancher/k3s:v1.24.3-k3s1"


def test_d_services_available(minikube: AClusterManager):
    data = get_beiboot_data(BEIBOOT_NAME, minikube)
    output = minikube.kubectl(["-n", data["beibootNamespace"], "get", "svc"])
    svc_names = [svc["metadata"]["name"] for svc in output["items"]]
    assert len(svc_names) == 7
    assert "beiboot-tunnel-443" in svc_names
    assert "beiboot-tunnel-6443" in svc_names
    assert "beiboot-tunnel-80" in svc_names
    assert "port-443" in svc_names
    assert "port-6443" in svc_names
    assert "port-80" in svc_names
    assert "kubeapi" in svc_names
