from time import sleep

import pytest

from beiboot import api
from beiboot.connection.types import ConnectorType
from beiboot.types import BeibootRequest, BeibootParameters, BeibootState
from tests.e2e.base import TestClientBase


class TestConnectSetup(TestClientBase):
    def test_connect_ghostunnel_docker(self, operator, kubectl, timeout):
        bbt = api.create(
            BeibootRequest(
                name="cluster1",
                parameters=BeibootParameters(
                    nodes=1,
                    serverStorageRequests="500Mi",
                    serverResources={"requests": {"cpu": "0.5", "memory": "0.5Gi"}},
                    nodeResources={"requests": {"cpu": "0.5", "memory": "0.5Gi"}},
                ),
            )
        )
        with pytest.raises(RuntimeError):
            _ = api.connect(bbt, ConnectorType.GHOSTUNNEL_DOCKER)

        bbt.wait_for_state(awaited_state=BeibootState.READY, timeout=timeout)
        _ = api.connect(bbt, ConnectorType.GHOSTUNNEL_DOCKER)
        sleep(2)
        _ = api.terminate(bbt.name, ConnectorType.GHOSTUNNEL_DOCKER)
