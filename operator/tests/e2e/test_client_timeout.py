import logging
from datetime import datetime
from time import sleep

from pytest_kubernetes.providers import AClusterManager

from tests.e2e.base import TestOperatorBase


class TestOperatorSunset(TestOperatorBase):
    beiboot_name = "test-beiboot-timeout"

    def test_beiboot_no_connect_timeout(self, operator: AClusterManager, timeout):
        minikube = operator
        kubectl = minikube.kubectl
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

    def test_beiboot_one_connect_timeout(self, operator: AClusterManager, timeout, core_api):
        import kubernetes as k8s
        from beiboot.comps.client_timeout import CONFIGMAP_NAME

        minikube = operator
        kubectl = minikube.kubectl

        self._apply_fixure_file("tests/fixtures/timeout-beiboot.yaml", kubectl, timeout)
        # READY state
        self._wait_for_state("READY", kubectl, timeout * 2)
        beiboot = self._get_beiboot_data(kubectl)
        assert beiboot["parameters"]["maxSessionTimeout"] == "10s"
        assert "lastClientContact" not in beiboot

        logging.getLogger().info("Writing heartbeat from client")
        time = datetime.utcnow()
        logging.info("Writing latest connect: " + str(time.isoformat()))
        configmap = k8s.client.V1ConfigMap(
            api_version="v1",
            kind="ConfigMap",
            data={"tester": time.isoformat()},
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
        sleep(8)
        beiboot = self._get_beiboot_data(kubectl)
        assert (
            beiboot["lastClientContact"]
            == time.isoformat(timespec="microseconds") + "Z"
        )
        sleep(20)

        namespaces = kubectl(["get", "ns"])
        assert (
            beiboot["beibootNamespace"] not in namespaces or "Terminating" in namespaces
        )
