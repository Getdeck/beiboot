from beiboot import api
from beiboot.types import BeibootRequest
from tests.e2e.base import TestClientBase


class TestBaseSetup(TestClientBase):

    beiboot_name = "mycluster"

    def test_simple_beiboot(self, operator, kubectl, timeout):
        req = BeibootRequest(name="mycluster")
        bbt = api.create(req)
        bbt_raw = self._get_beiboot_data(kubectl)
        assert bbt_raw["metadata"]["name"] == self.beiboot_name
        assert bbt.name == self.beiboot_name
        assert bbt.namespace == "getdeck-bbt-mycluster"
