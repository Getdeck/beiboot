from beiboot import api
from beiboot.types import BeibootRequest, BeibootState
from tests.e2e.base import TestClientBase


class TestConnectSetup(TestClientBase):
    def test_get_connection_data(self, operator, kubectl, timeout):
        bbt = api.create(BeibootRequest(name="cluster1"))
        bbt.wait_for_state(awaited_state=BeibootState.READY)
        mtls = bbt.mtls_files
        assert mtls is not None
        assert "ca.crt" in mtls.keys()
        assert "client.crt" in mtls.keys()
        assert "client.key" in mtls.keys()
        assert bool(mtls["ca.crt"]) is True
        assert bool(mtls["client.crt"]) is True
        assert bool(mtls["client.key"]) is True

        kubeconfig = bbt.kubeconfig
        assert bool(kubeconfig) is True

        serviceaccount_tokens = bbt.serviceaccount_tokens
        assert serviceaccount_tokens["namespace"] == "getdeck-bbt-cluster1"
        assert bool(serviceaccount_tokens) is True
        assert bool(serviceaccount_tokens["ca.crt"]) is True
        assert bool(serviceaccount_tokens["token"]) is True
