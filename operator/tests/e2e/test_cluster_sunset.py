from time import sleep

from tests.e2e.base import TestOperatorBase


class TestOperatorSunset(TestOperatorBase):
    beiboot_name = "test-beiboot-sunset"

    def test_beiboot_sunset(self, operator, kubectl, timeout):
        self._apply_fixure_file("tests/fixtures/sunset-beiboot.yaml", kubectl, timeout)
        # READY state
        self._wait_for_state("READY", kubectl, timeout * 2)
        beiboot = self._get_beiboot_data(kubectl)
        sleep(1)
        assert beiboot["sunset"] is not None
        sleep(60)
        namespaces = kubectl(["get", "ns"])
        assert (
            beiboot["beibootNamespace"] not in namespaces or "Terminating" in namespaces
        )
