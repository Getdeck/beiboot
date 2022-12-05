import logging
from time import sleep

from kopf.testing import KopfRunner

from tests.e2e.base import TestOperatorBase


class TestOperator(TestOperatorBase):
    beiboot_name = "test-beiboot"

    def test_create_simple_beiboot(self, operator, kubectl, timeout, caplog):

        self._apply_fixure_file("tests/fixtures/simple-beiboot.yaml", kubectl, timeout)
        # PENDING state
        self._wait_for_state("PENDING", kubectl, timeout)
        # RUNNING state
        self._wait_for_state("RUNNING", kubectl, timeout)
        # READY state
        self._wait_for_state("READY", kubectl, timeout)

    def test_extract_tunnel_data(self, kubectl):
        data = self._get_beiboot_data(kubectl)
        assert "tunnel" in data
        assert "gefyra" in data["parameters"]
        assert "port" in data["gefyra"] and bool(data["gefyra"]["port"])
        assert "127.0.0.1" in data["gefyra"]["endpoint"]
        assert "ghostunnel" in data["tunnel"]
        assert "mtls" in data["tunnel"]["ghostunnel"]
        assert "client.crt" in data["tunnel"]["ghostunnel"]["mtls"] and bool(
            data["tunnel"]["ghostunnel"]["mtls"]["client.crt"]
        )
        assert "ca.crt" in data["tunnel"]["ghostunnel"]["mtls"] and bool(
            data["tunnel"]["ghostunnel"]["mtls"]["ca.crt"]
        )
        assert "client.key" in data["tunnel"]["ghostunnel"]["mtls"] and bool(
            data["tunnel"]["ghostunnel"]["mtls"]["client.key"]
        )
        assert "ports" in data["tunnel"]["ghostunnel"]
        assert "serviceaccount" in data["tunnel"]
