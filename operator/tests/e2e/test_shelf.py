from pathlib import Path

import kubernetes
from pytest_kubernetes.providers import AClusterManager

from tests.utils import get_shelf_data

BEIBOOT_NAME = "test-shelf-beiboot"
BEIBOOT_NAME_RESTORE = "test-shelf-beiboot-restore"
SHELF_NAME = "test-shelf"


def test_a_create_simple_beiboot(operator: AClusterManager, timeout):
    minikube = operator
    minikube.apply(Path("tests/fixtures/shelf-beiboot.yaml"))
    # READY state
    minikube.wait(
        f"beiboots.getdeck.dev/{BEIBOOT_NAME}",
        "jsonpath=.state=READY",
        namespace="getdeck",
        timeout=timeout,
    )


def test_b_create_shelf(operator: AClusterManager, timeout, caplog):
    minikube = operator
    # ensure that volumesnapshotclass is there
    # TODO: is there a better condition?
    minikube.wait(
        "volumesnapshotclasses.snapshot.storage.k8s.io/csi-hostpath-snapclass",
        "jsonpath=.metadata.name=csi-hostpath-snapclass",
        timeout=timeout,
    )
    minikube.apply(Path("tests/fixtures/shelf.yaml"))
    # PENDING state
    minikube.wait(
        f"shelves.beiboots.getdeck.dev/{SHELF_NAME}",
        "jsonpath=.state=PENDING",
        namespace="getdeck",
        timeout=timeout,
    )
    # READY state
    #  when this is reached, we implicitly know, that the VolumeSnapshots and VolumeSnapshotContents are created and
    #  ready
    minikube.wait(
        f"shelves.beiboots.getdeck.dev/{SHELF_NAME}",
        "jsonpath=.state=READY",
        namespace="getdeck",
        timeout=timeout,
    )
    data = get_shelf_data(SHELF_NAME, minikube)
    assert data["metadata"]["name"] == SHELF_NAME
    assert len(data["volumeSnapshotContents"]) == 3
    snapshot_handles = [vsc["snapshotHandle"] for vsc in data["volumeSnapshotContents"]]
    # assert that no snapshot handle is empty
    assert all(snapshot_handles)
    assert len(data["clusterParameters"]) > 0
    assert data["clusterParameters"]["nodes"] == 3


# TODO: this test is not working yet, for unclear reasons (restored VolumesnapshotContents don't get ready, no logs
#  that help to further investigate); manually it doesn't work either on minikube, but it works for example on a Hetzner
#  (kubeone) cluster...
# def test_c_restore_shelf(operator: AClusterManager, timeout):
#     minikube = operator
#     minikube.apply(Path("tests/fixtures/shelf-beiboot-restore.yaml"))
#     # READY state
#     minikube.wait(
#         f"beiboots.getdeck.dev/{BEIBOOT_NAME_RESTORE}",
#         "jsonpath=.state=READY",
#         namespace="getdeck",
#         timeout=480,
#     )
#     # minikube.wait(f"ns/getdeck", "delete", timeout=120)
#
#     data = get_beiboot_data(BEIBOOT_NAME_RESTORE, minikube)
#     # assert data.keys() == 1
#     assert data["parameters"]["nodes"] == 3
#     assert data["parameters"]["ports"] == ["8080:80", "8443:443", "6443:6443"]
#     assert data["parameters"]["serverStorageRequests"] == "500Mi"
#     assert data["parameters"]["nodeStorageRequests"] == "500Mi"


def test_d_delete_shelf(operator: AClusterManager, timeout):
    minikube = operator
    # create additional dummy VolumeSnapshotContent with same shelf-uid label to check whether it is deleted
    minikube.apply(Path("tests/fixtures/volume-snapshot-content.yaml"))
    shelf = minikube.kubectl(["get", "shelf", SHELF_NAME, "-n", "getdeck"])
    shelf_uid = shelf["metadata"]["uid"]
    body = {
        "metadata": {"labels": {"shelf-uid": shelf_uid}},
    }
    kubernetes.config.load_kube_config(config_file=str(minikube.kubeconfig))
    custom_api = kubernetes.client.CustomObjectsApi()
    custom_api.patch_cluster_custom_object(
        group="snapshot.storage.k8s.io",
        version="v1",
        plural="volumesnapshotcontents",
        name="test",
        body=body,
    )

    vsc_list = minikube.kubectl(
        ["get", "volumesnapshotcontents.snapshot.storage.k8s.io"]
    )
    minikube.kubectl(["delete", "shelf", SHELF_NAME, "-n", "getdeck"], as_dict=False)
    # assert that VolumeSnapshotContents are deleted
    for vsc in vsc_list["items"]:
        minikube.wait(
            f"volumesnapshotcontents.snapshot.storage.k8s.io/{vsc['metadata']['name']}",
            "delete",
            timeout=30,
        )
