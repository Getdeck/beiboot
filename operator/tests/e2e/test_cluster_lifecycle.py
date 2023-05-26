from pathlib import Path
from time import sleep

import pytest
from pytest_kubernetes.providers import AClusterManager

from tests.e2e.base import TestOperatorBase


class TestOperator(TestOperatorBase):
    beiboot_name = "test-beiboot-configured"

    def test_beiboot_lifecycle(self, operator: AClusterManager, kubectl, timeout):
        minikube = operator
        minikube.apply(Path("tests/fixtures/configured-beiboot.yaml"))
        # READY state
        minikube.wait(
            "beiboot.getdeck.dev/test-beiboot-configured",
            "jsonpath=.state=READY",
            namespace="getdeck",
            timeout=timeout * 2,
        )
        # self._wait_for_state("READY", kubectl, timeout * 2)
        beiboot = self._get_beiboot_data(kubectl)
        sleep(2)
        kubectl(["-n", beiboot["beibootNamespace"], "delete", "pod", "server-0"])
        self._wait_for_state("ERROR", kubectl, timeout)
        kubectl(["-n", "getdeck", "delete", "bbt", self.beiboot_name])
        sleep(2)
        namespaces = kubectl(["get", "ns"])
        assert (
            beiboot["beibootNamespace"] not in namespaces or "Terminating" in namespaces
        )
        with pytest.raises(RuntimeError):
            _ = self._get_beiboot_data(kubectl)
