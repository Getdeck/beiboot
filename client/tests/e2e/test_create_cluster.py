from time import sleep

import pytest

from beiboot import api
from beiboot.types import BeibootRequest, BeibootParameters
from tests.e2e.base import TestClientBase

from beiboot.types import BeibootState


class TestBaseSetup(TestClientBase):

    beiboot_name = "mycluster"

    def test_simple_beiboot(self, operator, kubectl, timeout):
        req = BeibootRequest(
            name=self.beiboot_name,
            parameters=BeibootParameters(
                nodes=1,
                serverStorageRequests="500Mi",
                serverResources={"requests": {"cpu": "0.5", "memory": "0.5Gi"}},
                nodeResources={"requests": {"cpu": "0.5", "memory": "0.5Gi"}},
            ),
        )
        bbt = api.create(req)

        bbt.wait_for_state(awaited_state=BeibootState.PENDING)
        bbt_raw = self._get_beiboot_data(kubectl)
        assert bbt_raw["state"] in [
            BeibootState.CREATING.value,
            BeibootState.PENDING.value,
        ]
        assert bbt.state in [BeibootState.CREATING, BeibootState.PENDING]

        assert bbt.name == self.beiboot_name
        assert bbt.namespace == self.get_target_namespace()
        assert bbt.transitions is not None

        bbt.wait_for_state(awaited_state=BeibootState.RUNNING)
        assert bbt.state == BeibootState.RUNNING

        a_bbt = api.read(self.beiboot_name)
        assert a_bbt.uid == bbt.uid
        assert a_bbt.state == bbt.state

        api.delete(bbt)
        # bbt.wait_for_state(awaited_state=BeibootState.TERMINATING)
        # assert bbt.state == BeibootState.TERMINATING
        sleep(1)
        with pytest.raises(RuntimeError):
            _ = self._get_beiboot_data(kubectl)