from beiboot import api
from beiboot.types import BeibootRequest, BeibootParameters
from tests.e2e.base import TestClientBase


class TestBaseSetup(TestClientBase):
    def test_list_clusters(self, operator, kubectl, timeout):
        req1 = BeibootRequest(
            name="cluster1",
            parameters=BeibootParameters(
                nodes=1,
                serverStorageRequests="500Mi",
                serverResources={"requests": {"cpu": 0.5, "memory": "0.5Gi"}},
                nodeResources={"requests": {"cpu": 0.5, "memory": "0.5Gi"}},
            ),
        )
        req2 = BeibootRequest(
            name="cluster2",
            parameters=BeibootParameters(
                nodes=1,
                serverStorageRequests="500Mi",
                serverResources={"requests": {"cpu": 0.5, "memory": "0.5Gi"}},
                nodeResources={"requests": {"cpu": 0.5, "memory": "0.5Gi"}},
            ),
        )
        _ = api.create(req1)
        _ = api.create(req2)

        clusters = api.read_all()
        for beiboot in clusters:
            assert beiboot.name in ["cluster1", "cluster2"]
