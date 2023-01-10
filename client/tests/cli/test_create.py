import pytest

from click.testing import CliRunner

from beiboot import api
from beiboot.configuration import ClientConfiguration
from beiboot.types import BeibootState
from cli.cluster import create_cluster


def test_create_no_beiboot(minikube):
    runner = CliRunner()
    result = runner.invoke(
        create_cluster,  # noqa
        ["my-test"],
        obj={"config": ClientConfiguration()},
    )
    assert result.exit_code == 1


def test_a_create_beiboot_object(crds):
    runner = CliRunner()
    result = runner.invoke(
        create_cluster,  # noqa
        ["my-test", "--nodes", "2", "--max-session-timeout", "8h", "--nowait"],
        obj={"config": ClientConfiguration()},
    )
    assert result.exit_code == 0
    assert not result.exception

    beiboot = api.read("my-test")
    assert beiboot.state == BeibootState.REQUESTED
    assert beiboot.parameters.nodes == 2
    assert beiboot.parameters.maxSessionTimeout == "8h"


def test_b_create_beiboot_object(crds):
    runner = CliRunner()
    result = runner.invoke(
        create_cluster,  # noqa
        [
            "my-test1",
            "--server-requests-cpu",
            "2000m",
            "--server-requests-memory",
            "4Gi",
            "--node-requests-cpu",
            "3",
            "--node-requests-memory",
            "4.5Gi",
            "--nowait",
        ],
        obj={"config": ClientConfiguration()},
    )
    assert result.exit_code == 0
    assert not result.exception

    beiboot = api.read("my-test1")
    assert "requests" in beiboot.parameters.serverResources  # type: ignore
    assert beiboot.parameters.serverResources["requests"]["cpu"] == "2000m"  # type: ignore
    assert beiboot.parameters.serverResources["requests"]["memory"] == "4Gi"  # type: ignore
    assert "requests" in beiboot.parameters.nodeResources  # type: ignore
    assert beiboot.parameters.nodeResources["requests"]["cpu"] == "3"  # type: ignore
    assert beiboot.parameters.nodeResources["requests"]["memory"] == "4.5Gi"  # type: ignore

    with pytest.raises(RuntimeError):
        beiboot = api.read("my-test2")


def test_c_create_beiboot_object(crds):
    runner = CliRunner()
    result = runner.invoke(
        create_cluster,  # noqa
        ["my-test1"],
        obj={"config": ClientConfiguration()},
    )
    assert result.exit_code == 1
    print(result.stdout)
