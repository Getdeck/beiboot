from beiboot import api
from beiboot.types import ShelfRequest
from tests.e2e.base import EnsureBeibootMixin, TestClientBase


class TestBaseSetup(EnsureBeibootMixin, TestClientBase):
    def test_list_shelves(self, operator, kubectl, timeout):
        bbt = self._ensure_beiboot("cluster1", minikube_ip=None, timeout=timeout)

        req1 = ShelfRequest(
            name="shelf1",
            cluster_name=bbt.name,
            volume_snapshot_class="csi-hostpath-snapclass",
            volume_snapshot_contents=[],
            labels={},
        )
        req2 = ShelfRequest(
            name="shelf2",
            cluster_name=bbt.name,
            volume_snapshot_class="csi-hostpath-snapclass",
            volume_snapshot_contents=[],
            labels={},
        )
        _ = api.create_shelf(req1)
        _ = api.create_shelf(req2)

        shelves = api.read_all_shelves()
        for shelf in shelves:
            assert shelf.name in ["shelf1", "shelf2"]
