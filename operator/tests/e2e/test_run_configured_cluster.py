import logging
from time import sleep

from kopf.testing import KopfRunner

from tests.e2e.base import TestOperatorBase


class TestOperatorConfigured(TestOperatorBase):
    beiboot_name = "test-beiboot-configured"

    def test_create_configured_beiboot(self, kubeconfig, kubectl, timeout, caplog):
        caplog.set_level(logging.INFO, logger="kopf")
        self._ensure_namespace(kubectl)
        with KopfRunner(["run", "-A", "main.py"]) as runner:
            sleep(5)
            self._apply_fixure_file(
                "tests/fixtures/configured-beiboot.yaml", kubectl, timeout
            )
            # READY state
            self._wait_for_state("READY", kubectl, timeout * 2)

        assert runner.exit_code == 0
        assert runner.exception is None

    def test_gefyra_disabled(self, kubectl):
        data = self._get_beiboot_data(kubectl)
        assert data["parameters"]["gefyra"]["enabled"] is False
        assert data["parameters"]["gefyra"].get("endpoint") is None
        assert data["parameters"]["gefyra"].get("port") is None

    def test_parameters_set(self, kubectl):
        data = self._get_beiboot_data(kubectl)
        assert data["parameters"]["nodes"] == 3
        assert data["parameters"]["maxLifetime"] == "10s"
        assert data["parameters"]["ports"] == ["8080:80", "8443:443"]

    def test_services_available(self, kubectl):
        data = self._get_beiboot_data(kubectl)
        output = kubectl(["-n", data["beibootNamespace"], "get", "svc"])
        lines = list(
            map(lambda x: x.split()[0], [_l for _l in output.split("\n")[1:] if _l])
        )
        assert len(lines) == 7
        assert "beiboot-tunnel-443" in lines
        assert "beiboot-tunnel-6443" in lines
        assert "beiboot-tunnel-80" in lines
        assert "port-443" in lines
        assert "port-6443" in lines
        assert "port-80" in lines
        assert "kubeapi" in lines
