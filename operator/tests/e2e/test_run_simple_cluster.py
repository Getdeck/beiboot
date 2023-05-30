from pathlib import Path

from pytest_kubernetes.providers import AClusterManager

from tests.utils import get_beiboot_data


BEIBOOT_NAME = "test-beiboot"


def test_a_create_simple_beiboot(operator: AClusterManager, timeout, caplog):
    minikube = operator
    minikube.apply(Path("tests/fixtures/simple-beiboot.yaml"))
    # PENDING state
    minikube.wait(
        f"beiboots.getdeck.dev/{BEIBOOT_NAME}",
        "jsonpath=.state=PENDING",
        namespace="getdeck",
        timeout=120,
    )
    # RUNNING state
    minikube.wait(
        f"beiboots.getdeck.dev/{BEIBOOT_NAME}",
        "jsonpath=.state=RUNNING",
        namespace="getdeck",
        timeout=120,
    )
    # READY state
    minikube.wait(
        f"beiboots.getdeck.dev/{BEIBOOT_NAME}",
        "jsonpath=.state=READY",
        namespace="getdeck",
        timeout=120,
    )


def test_b_extract_tunnel_data(minikube: AClusterManager):
    data = get_beiboot_data(BEIBOOT_NAME, minikube)
    assert "tunnel" in data
    assert "gefyra" in data["parameters"]
    assert "port" in data["gefyra"] and bool(data["gefyra"]["port"])
    assert "127.0.0.1" in data["gefyra"]["endpoint"]
    assert "ghostunnel" in data["tunnel"]
    assert "mtls" in data["tunnel"]["ghostunnel"]
    assert "client.crt" in data["tunnel"]["ghostunnel"]["mtls"] and bool(
        data["tunnel"]["ghostunnel"]["mtls"]["client.crt"]
    )
    assert "ca.crt" in data["tunnel"]["ghostunnel"]["mtls"] and bool(
        data["tunnel"]["ghostunnel"]["mtls"]["ca.crt"]
    )
    assert "client.key" in data["tunnel"]["ghostunnel"]["mtls"] and bool(
        data["tunnel"]["ghostunnel"]["mtls"]["client.key"]
    )
    assert "ports" in data["tunnel"]["ghostunnel"]
    assert "serviceaccount" in data["tunnel"]
