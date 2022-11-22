import logging
from time import sleep

from kopf.testing import KopfRunner

from tests.e2e.base import TestOperatorBase


class TestOperatorConfigured(TestOperatorBase):
    beiboot_name = "test-beiboot-configured"

    def test_create_configured_beiboot(self, kubeconfig, kubectl, timeout, caplog):
        caplog.set_level(logging.CRITICAL, logger="kopf")
        self._ensure_namespace(kubectl)
        with KopfRunner(["run", "-n", "getdeck", "main.py"]) as runner:
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
        assert data["gefyra"]["enabled"] is False
        assert data["gefyra"].get("endpoint") is None
        assert data["gefyra"].get("port") is None

    def test_services_available(self, kubectl):
        data = self._get_beiboot_data(kubectl)
        output = kubectl(["-n", data["beibootNamespace"], "get", "svc"])
        lines = list(map(lambda x: x.split()[0], output.split("\n")[1:]))
        logging.getLogger().info(lines)
        assert len(lines) == 7
        assert "beiboot-tunnel-443" in lines
        assert "beiboot-tunnel-6443" in lines
        assert "beiboot-tunnel-80" in lines
        assert "port-443" in lines
        assert "port-6443" in lines
        assert "port-80" in lines
        assert "kubeapi" in lines


