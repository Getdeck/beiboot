import pytest
from time import sleep

from beiboot import api
from beiboot.types import BeibootRequest, BeibootParameters, ShelfRequest
from tests.e2e.base import TestClientBase

import kubernetes

from beiboot.types import ShelfState, BeibootState


class TestBaseSetup(TestClientBase):

    beiboot_name = "mycluster"

    def test_create_cluster(self, operator, timeout):
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
        bbt.wait_for_state(awaited_state=BeibootState.READY, timeout=timeout)

    @pytest.mark.parametrize(
        "shelf_name,valid", [("shelf_test", False), ("shelftest", True)]
    )
    def test_shelf_names(self, shelf_name, valid, operator, timeout):

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

    def test_shelf_create(self, operator, timeout):
        minikube = operator
        shelf_name = "shelftest2"
        shelf_req = ShelfRequest(
            name=shelf_name,
            cluster_name=self.beiboot_name,
            volume_snapshot_class="csi-hostpath-snapclass",
            volume_snapshot_contents=[],
            labels={},
        )
        shelf = api.create_shelf(shelf_req)
        shelf.wait_for_state(awaited_state=ShelfState.PENDING, timeout=timeout)
        shelf_raw = self._get_shelf_data(minikube.kubectl, shelf_name)
        assert shelf_raw["state"] in [
            ShelfState.CREATING.value,
            ShelfState.PENDING.value,
        ]
        assert shelf.state in [ShelfState.CREATING, ShelfState.PENDING]

        assert shelf.name == shelf_name
        assert shelf.volume_snapshot_contents not in [None, []]
        assert shelf.transitions is not None

        shelf.wait_for_state(awaited_state=ShelfState.READY, timeout=timeout)
        assert shelf.state == ShelfState.READY

        a_shelf = api.read_shelf(shelf_name)
        assert a_shelf.uid == shelf.uid
        assert a_shelf.state == shelf.state

        api.delete_shelf(shelf)
        # shelf.wait_for_state(awaited_state=ShelfState.TERMINATING)
        # assert shelf.state == ShelfState.TERMINATING
        sleep(5)
        with pytest.raises(RuntimeError):
            _ = self._get_shelf_data(minikube.kubectl, shelf_name)
