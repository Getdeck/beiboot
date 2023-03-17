import pytest

from beiboot import api
from beiboot.types import BeibootRequest, BeibootParameters, ShelfRequest
from tests.e2e.base import TestClientBase

import kubernetes

from beiboot.types import ShelfState, BeibootState


class TestBaseSetup(TestClientBase):

    beiboot_name = "mycluster"

    def test_create_cluster(self, operator, kubectl, timeout):
        req = BeibootRequest(
            name=self.beiboot_name,
            parameters=BeibootParameters(
                nodes=1,
                serverStorageRequests="500Mi",
                serverResources={"requests": {"cpu": "0.25", "memory": "0.25Gi"}},
                nodeResources={"requests": {"cpu": "0.25", "memory": "0.25Gi"}},
            ),
        )
        bbt = api.create(req)
        bbt.wait_for_state(awaited_state=BeibootState.PENDING, timeout=timeout)

    @pytest.mark.parametrize(
        "shelf_name,valid", [("shelf_test", False), ("shelftest", True)]
    )
    def test_shelf_names(self, shelf_name, valid, operator, kubectl, timeout):

        shelf_req = ShelfRequest(
            name=shelf_name,
            cluster_name=self.beiboot_name,
        )
        if valid:
            try:
                api.create_shelf(shelf_req)
            except kubernetes.client.exceptions.ApiException:
                pytest.fail(
                    "This should have not been failed: The name is considered valid"
                )

            assert len(api.read_all_shelves()) == 1
        else:
            with pytest.raises(kubernetes.client.exceptions.ApiException):
                api.create_shelf(shelf_req)
            assert len(api.read_all_shelves()) == 0

    def test_shelf_create(self, operator, kubectl, timeout):

        shelf_req = ShelfRequest(
            name="shelftest2",
            cluster_name=self.beiboot_name,
            volume_snapshot_class="csi-hostpath-snapclass",
            volume_snapshot_contents=[],
            labels={},
        )
        shelf = api.create_shelf(shelf_req)
        shelf.wait_for_state(awaited_state=ShelfState.READY, timeout=2400)
