from time import sleep

import pytest
from pytest_kubernetes.providers import AClusterManager

from beiboot import api
from beiboot.types import BeibootRequest, BeibootParameters
from tests.e2e.base import TestClientBase

from beiboot.types import BeibootState


class TestBaseSetup(TestClientBase):

    beiboot_name = "mycluster"

    def test_simple_beiboot(self, operator: AClusterManager, timeout):
        minikube = operator
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
        bbt_raw = self._get_beiboot_data(minikube.kubectl)
        assert bbt_raw["state"] in [
            BeibootState.CREATING.value,
            BeibootState.PENDING.value,
        ]
        assert bbt.state in [BeibootState.CREATING, BeibootState.PENDING]

        assert bbt.name == self.beiboot_name
        assert bbt.namespace == self.get_target_namespace()
        assert bbt.transitions is not None

        bbt.wait_for_state(awaited_state=BeibootState.RUNNING, timeout=timeout)
        assert bbt.state == BeibootState.RUNNING

        a_bbt = api.read(self.beiboot_name)
        assert a_bbt.uid == bbt.uid
        assert a_bbt.state == bbt.state

        api.delete(bbt)
        # bbt.wait_for_state(awaited_state=BeibootState.TERMINATING)
        # assert bbt.state == BeibootState.TERMINATING
        sleep(5)
        with pytest.raises(RuntimeError):
            _ = self._get_beiboot_data(minikube.kubectl)
