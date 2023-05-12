from time import sleep

from beiboot import api
from beiboot.connection.types import ConnectorType
from tests.e2e.base import TestClientBase, EnsureBeibootMixin


class TestConnectSetup(EnsureBeibootMixin, TestClientBase):
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
