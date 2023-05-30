from pathlib import Path
from time import sleep

from pytest_kubernetes.providers import AClusterManager

from tests.utils import get_beiboot_data

BEIBOOT_NAME = "test-beiboot-sunset"


def test_beiboot_sunset(operator: AClusterManager, timeout):
    minikube = operator
    minikube.apply(Path("tests/fixtures/sunset-beiboot.yaml"))
    # READY state
    minikube.wait(
        f"beiboots.getdeck.dev/{BEIBOOT_NAME}",
        "jsonpath=.state=READY",
        namespace="getdeck",
        timeout=120,
    )
    beiboot = get_beiboot_data(BEIBOOT_NAME, minikube)
    sleep(1)
    assert beiboot["sunset"] is not None
    sleep(15)
    # this Beiboot should terminate due to no client connecting for 10 seconds
    minikube.wait(f"ns/{beiboot['beibootNamespace']}", "delete", timeout=30)
