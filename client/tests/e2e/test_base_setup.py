from pathlib import Path

from pytest_kubernetes.providers import AClusterManager

from tests.e2e.base import TestClientBase


class TestBaseSetup(TestClientBase):

    beiboot_name = "test-beiboot"

    def test_sane_operator(self, operator: AClusterManager, timeout):
        minikube = operator
        minikube.apply(Path("tests/fixtures/simple-beiboot.yaml"))
        # READY state
        minikube.wait(
            f"beiboots.getdeck.dev/{self.beiboot_name}",
            "jsonpath=.state=READY",
            namespace="getdeck",
            timeout=120,
        )
        _ = self._get_beiboot_data(minikube.kubectl)
