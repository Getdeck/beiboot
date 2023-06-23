from pathlib import Path
from time import sleep

import pytest
from pytest_kubernetes.providers import AClusterManager

from tests.utils import get_beiboot_data


BEIBOOT_NAME = "test-beiboot-configured"


def test_beiboot_lifecycle(operator: AClusterManager, timeout):
    minikube = operator
    minikube.apply(Path("tests/fixtures/configured-beiboot.yaml"))
    # READY state
    minikube.wait(
        f"beiboot.getdeck.dev/{BEIBOOT_NAME}",
        "jsonpath=.state=READY",
        namespace="getdeck",
        timeout=120,
    )
    beiboot = get_beiboot_data(BEIBOOT_NAME, minikube)
    sleep(2)
    minikube.kubectl(
        ["-n", beiboot["beibootNamespace"], "delete", "pod", "server-0"], as_dict=False
    )
    minikube.wait(
        f"beiboot.getdeck.dev/{BEIBOOT_NAME}",
        "jsonpath=.state=ERROR",
        namespace="getdeck",
        timeout=120,
    )
    minikube.kubectl(["-n", "getdeck", "delete", "bbt", BEIBOOT_NAME], as_dict=False)
    sleep(2)
    # this Beiboot should terminate due to no client connecting for 10 seconds
    minikube.wait(f"ns/{beiboot['beibootNamespace']}", "delete", timeout=30)
    with pytest.raises(RuntimeError):
        _ = get_beiboot_data(BEIBOOT_NAME, minikube)
