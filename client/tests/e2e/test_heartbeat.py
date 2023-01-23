from datetime import datetime
import json

from beiboot import api
from beiboot.types import BeibootRequest, BeibootParameters
from tests.e2e.base import TestClientBase

from beiboot.types import BeibootState
from beiboot.configuration import default_configuration


class TestBaseSetup(TestClientBase):

    beiboot_name = "mycluster-hb"

    def test_write_heartbeat(self, operator, kubectl, timeout):

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

        timestamp = datetime.utcnow()

        api.write_heartbeat("test-client", bbt, timestamp)
        configmap = kubectl(
            [
                "-n",
                bbt.namespace,
                "get",
                "configmap",
                default_configuration.CLIENT_HEARTBEAT_CONFIGMAP_NAME,
                "--output",
                "json",
            ]
        )
        cm = json.loads(configmap)
        assert "test-client" in cm["data"].keys()
        assert cm["data"]["test-client"] == str(timestamp.isoformat())

        api.write_heartbeat("test-client1", bbt)
        configmap = kubectl(
            [
                "-n",
                bbt.namespace,
                "get",
                "configmap",
                default_configuration.CLIENT_HEARTBEAT_CONFIGMAP_NAME,
                "--output",
                "json",
            ]
        )
        cm = json.loads(configmap)
        assert "test-client1" in cm["data"].keys()
        assert datetime.fromisoformat(cm["data"]["test-client1"])
