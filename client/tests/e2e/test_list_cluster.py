from beiboot import api
from beiboot.types import BeibootRequest
from tests.e2e.base import TestClientBase


class TestBaseSetup(TestClientBase):
    def test_list_clusters(self, operator, kubectl, timeout):
        req1 = BeibootRequest(name="cluster1")
        req2 = BeibootRequest(name="cluster2")
        _ = api.create(req1)
        _ = api.create(req2)

        clusters = api.read_all()
        for beiboot in clusters:
            assert beiboot.name in ["cluster1", "cluster2"]
