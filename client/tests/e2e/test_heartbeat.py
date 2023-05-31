from datetime import datetime
import json

from pytest_kubernetes.providers import AClusterManager

from beiboot import api
from beiboot.types import BeibootRequest, BeibootParameters
from tests.e2e.base import TestClientBase

from beiboot.types import BeibootState
from beiboot.configuration import default_configuration


class TestBaseSetup(TestClientBase):

    beiboot_name = "mycluster-hb"

    def test_write_heartbeat(self, operator: AClusterManager, timeout):
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

        timestamp = datetime.utcnow()

        api.write_heartbeat("test-client", bbt, timestamp)
        configmap = minikube.kubectl(
            [
                "-n",
                bbt.namespace,
                "get",
                "configmap",
                default_configuration.CLIENT_HEARTBEAT_CONFIGMAP_NAME,
            ]
        )
        # cm = json.loads(configmap)
        assert "test-client" in configmap["data"].keys()
        assert configmap["data"]["test-client"] == str(timestamp.isoformat())

        api.write_heartbeat("test-client1", bbt)
        configmap = minikube.kubectl(
            [
                "-n",
                bbt.namespace,
                "get",
                "configmap",
                default_configuration.CLIENT_HEARTBEAT_CONFIGMAP_NAME,
            ]
        )
        # cm = json.loads(configmap)
        assert "test-client1" in configmap["data"].keys()
        assert datetime.fromisoformat(configmap["data"]["test-client1"])
