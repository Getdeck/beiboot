import logging
from datetime import datetime
from pathlib import Path
from time import sleep

from pytest_kubernetes.providers import AClusterManager

BEIBOOT_NAME = "test-beiboot-timeout"


def test_a_beiboot_no_connect_timeout(operator: AClusterManager, timeout):
    minikube = operator
    minikube.apply(Path("tests/fixtures/timeout-beiboot.yaml"))
    # READY state
    minikube.wait(
        f"beiboots.getdeck.dev/{BEIBOOT_NAME}",
        "jsonpath=.state=READY",
        namespace="getdeck",
        timeout=120,
    )
    beiboot = minikube.kubectl(["-n", "getdeck", "get", "bbt", "test-beiboot-timeout"])
    # this Beiboot should terminate due to no client connecting for 10 seconds
    minikube.wait(f"ns/{beiboot['beibootNamespace']}", "delete", timeout=30)


def test_b_beiboot_one_connect_timeout(operator: AClusterManager, timeout):
    import kubernetes as k8s
    from beiboot.comps.client_timeout import CONFIGMAP_NAME

    minikube = operator

    minikube.apply(Path("tests/fixtures/timeout-beiboot.yaml"))
    # READY state
    minikube.wait(
        f"beiboots.getdeck.dev/{BEIBOOT_NAME}",
        "jsonpath=.state=READY",
        namespace="getdeck",
        timeout=120,
    )
    beiboot = minikube.kubectl(["-n", "getdeck", "get", "bbt", BEIBOOT_NAME])
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
            namespace=f"getdeck-bbt-{BEIBOOT_NAME}",
        ),
    )

    k8s.client.CoreV1Api().patch_namespaced_config_map(
        name=CONFIGMAP_NAME,
        namespace=f"getdeck-bbt-{BEIBOOT_NAME}",
        body=configmap,
    )
    sleep(8)
    beiboot = minikube.kubectl(["-n", "getdeck", "get", "bbt", BEIBOOT_NAME])
    assert (
        beiboot["lastClientContact"]
        == time.isoformat(timespec="microseconds") + "Z"
    )
    # this Beiboot should terminate due to no client connecting for 10 seconds
    minikube.wait(f"ns/{beiboot['beibootNamespace']}", "delete", timeout=30)
