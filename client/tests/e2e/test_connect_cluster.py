import pytest

from beiboot import api
from beiboot.connection.types import ConnectorType
from beiboot.types import BeibootRequest, BeibootParameters, BeibootState, TunnelParams
from tests.e2e.base import TestClientBase


class TestConnectSetup(TestClientBase):
    def test_connect_ghostunnel_docker(
        self, operator, local_kubectl, minikube, minikube_ip, timeout
    ):
        bbt = api.create(
            BeibootRequest(
                name="cluster1",
                parameters=BeibootParameters(
                    nodes=1,
                    serverStorageRequests="100Mi",
                    serverResources={"requests": {"cpu": "0.25", "memory": "0.25Gi"}},
                    nodeResources={"requests": {"cpu": "0.25", "memory": "0.25Gi"}},
                    tunnel=TunnelParams(endpoint=minikube_ip),
                ),
            )
        )
        with pytest.raises(RuntimeError):
            _ = api.connect(bbt, ConnectorType.GHOSTUNNEL_DOCKER)

        bbt.wait_for_state(awaited_state=BeibootState.READY, timeout=timeout)
        connector = api.connect(
            bbt, ConnectorType.GHOSTUNNEL_DOCKER, _docker_network=minikube
        )
        location = connector.save_kubeconfig_to_file(bbt)
        assert location is not None
        output = local_kubectl(["get", "nodes"], location)
        assert "server-0" in output
        _ = api.terminate(bbt.name, ConnectorType.GHOSTUNNEL_DOCKER)
