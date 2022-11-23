from time import sleep

import pytest
from kopf.testing import KopfRunner

from tests.e2e.base import TestOperatorBase


class TestOperator(TestOperatorBase):
    beiboot_name = "test-beiboot-configured"

    def test_beiboot_lifecycle(self, kubeconfig, kubectl, timeout, caplog):
        # caplog.set_level(logging.CRITICAL, logger="kopf")
        self._ensure_namespace(kubectl)
        with KopfRunner(["run", "-A", "main.py"]) as runner:
            sleep(5)
            self._apply_fixure_file(
                "tests/fixtures/configured-beiboot.yaml", kubectl, timeout
            )
            # READY state
            self._wait_for_state("READY", kubectl, timeout * 2)
            beiboot = self._get_beiboot_data(kubectl)
            sleep(2)
            kubectl(["-n", beiboot["beibootNamespace"], "delete", "pod", "server-0"])
            self._wait_for_state("ERROR", kubectl, timeout)
            kubectl(["-n", "getdeck", "delete", "bbt", self.beiboot_name])
            sleep(2)
            namespaces = kubectl(["get", "ns"])
            assert (
                beiboot["beibootNamespace"] not in namespaces
                or "Terminating" in namespaces
            )
            with pytest.raises(RuntimeError):
                _ = self._get_beiboot_data(kubectl)

        assert runner.exit_code == 0
        assert runner.exception is None
