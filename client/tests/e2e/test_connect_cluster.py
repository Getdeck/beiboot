from time import sleep

import pytest

from beiboot import api
from beiboot.connection.types import ConnectorType
from beiboot.types import BeibootRequest, BeibootParameters, BeibootState, TunnelParams
from tests.e2e.base import TestClientBase


class TestConnectSetup(TestClientBase):
    @staticmethod
    def _ensure_beiboot(name, minikube_ip, timeout):
        try:
            bbt = api.read(name)
        except RuntimeError:
            bbt = api.create(
                BeibootRequest(
                    name=name,
                    parameters=BeibootParameters(
                        nodes=1,
                        serverStorageRequests="100Mi",
                        serverResources={
                            "requests": {"cpu": "0.25", "memory": "0.25Gi"}
                        },
                        nodeResources={"requests": {"cpu": "0.25", "memory": "0.25Gi"}},
                        tunnel=TunnelParams(endpoint=minikube_ip),
                    ),
                )
            )
            with pytest.raises(RuntimeError):
                _ = api.connect(bbt, ConnectorType.GHOSTUNNEL_DOCKER)
            bbt.wait_for_state(awaited_state=BeibootState.READY, timeout=timeout)
        return bbt

    @staticmethod
    def _remove_beiboot(name, wait=20):
        api.delete_by_name(name)
        sleep(wait)

    def test_connect_ghostunnel_docker(
        self, operator, local_kubectl, minikube, minikube_ip, timeout
    ):

        bbt = self._ensure_beiboot("cluster1", minikube_ip, timeout)
        connector = api.connect(
            bbt, ConnectorType.GHOSTUNNEL_DOCKER, _docker_network=minikube
        )
        location = connector.save_kubeconfig_to_file(bbt)
        assert location is not None
        output = local_kubectl(["get", "nodes"], location)
        assert "server-0" in output
        _ = api.terminate("cluster1", ConnectorType.GHOSTUNNEL_DOCKER)

    def test_connect_dummy_no_connect(self, operator, minikube, minikube_ip, timeout):
        bbt = self._ensure_beiboot("cluster1", minikube_ip, timeout)
        connector = api.connect(
            bbt,
            ConnectorType.DUMMY_NO_CONNECT,
        )
        location = connector.save_kubeconfig_to_file(bbt)
        assert location is not None
        _ = api.terminate("cluster1", ConnectorType.DUMMY_NO_CONNECT)
