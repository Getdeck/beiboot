from time import sleep

import pytest
from click.testing import CliRunner

from beiboot import api
from beiboot.configuration import ClientConfiguration
from beiboot.types import BeibootState
from cli import cluster


def test_create_delete_beiboot(operator):
    runner = CliRunner()
    result = runner.invoke(
        cluster.create_cluster,  # noqa
        [
            "test1",
            "--nodes",
            "1",
            "--server-requests-cpu",
            "0.25",
            "--server-requests-memory",
            "0.25Gi",
        ],
        obj={"config": ClientConfiguration()},
    )
    assert result.exit_code == 0
    assert not result.exception

    beiboot = api.read("test1")
    assert beiboot.state == BeibootState.READY
    assert beiboot.parameters.nodes == 1

    result = runner.invoke(
        cluster.delete_cluster, ["test1"], obj={"config": ClientConfiguration()}  # noqa
    )
    assert result.exit_code == 0
    assert not result.exception
    sleep(2)
    with pytest.raises(RuntimeError):
        api.read("test1")


def test_connect_beiboot(operator):
    pass
