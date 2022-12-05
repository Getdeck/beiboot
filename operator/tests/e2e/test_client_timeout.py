import logging
from datetime import datetime
from time import sleep

import kubernetes as k8s

from tests.e2e.base import TestOperatorBase


class TestOperatorSunset(TestOperatorBase):
    beiboot_name = "test-beiboot-timeout"

    def test_beiboot_no_connect_timeout(self, operator, kubectl, timeout):
        self._apply_fixure_file("tests/fixtures/timeout-beiboot.yaml", kubectl, timeout)
        # READY state
        self._wait_for_state("READY", kubectl, timeout * 2)
        beiboot = self._get_beiboot_data(kubectl)

        sleep(20)
        namespaces = kubectl(["get", "ns"])
        assert (
            beiboot["beibootNamespace"] not in namespaces or "Terminating" in namespaces
        )
        while True:
            namespaces = kubectl(["get", "ns"])
            if beiboot["beibootNamespace"] not in namespaces:
                break
            else:
                sleep(1)

    def test_beiboot_one_connect_timeout(self, operator, kubectl, timeout):
        from beiboot.comps.client_timeout import CONFIGMAP_NAME

        core_api = k8s.client.CoreV1Api()

        self._apply_fixure_file("tests/fixtures/timeout-beiboot.yaml", kubectl, timeout)
        # READY state
        self._wait_for_state("READY", kubectl, timeout * 2)
        beiboot = self._get_beiboot_data(kubectl)
        assert beiboot["parameters"]["maxSessionTimeout"] == "10s"

        logging.getLogger().info("Writing heartbeat from client")
        time = datetime.utcnow().isoformat()
        logging.info("Writing latest connect: " + str(time))
        configmap = k8s.client.V1ConfigMap(
            api_version="v1",
            kind="ConfigMap",
            data={"tester": time},
            metadata=k8s.client.V1ObjectMeta(
                name=CONFIGMAP_NAME,
                namespace="getdeck-bbt-test-beiboot-timeout",
            ),
        )
        core_api.patch_namespaced_config_map(
            name=CONFIGMAP_NAME,
            namespace="getdeck-bbt-test-beiboot-timeout",
            body=configmap,
        )
        sleep(20)

        namespaces = kubectl(["get", "ns"])
        assert (
                beiboot["beibootNamespace"] not in namespaces or "Terminating" in namespaces
        )