from tests.e2e.base import TestClientBase


class TestBaseSetup(TestClientBase):

    beiboot_name = "test-beiboot"

    def test_sane_operator(self, operator, kubectl, timeout):
        self._apply_fixture_file("tests/fixtures/simple-beiboot.yaml", kubectl, timeout)
        self._wait_for_state("READY", kubectl, timeout)
        _ = self._get_beiboot_data(kubectl)
