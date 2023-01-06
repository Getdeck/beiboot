from click.testing import CliRunner

from beiboot.configuration import ClientConfiguration
from cli.cluster import list_clusters


def test_list_no_beiboot(minikube):
    runner = CliRunner()
    result = runner.invoke(
        list_clusters,  # noqa
        obj={"config": ClientConfiguration()},
    )
    assert result.exit_code == 1


def test_list_empty(crds):
    runner = CliRunner()
    result = runner.invoke(
        list_clusters,  # noqa
        obj={"config": ClientConfiguration()},
    )
    assert result.exit_code == 0


def test_list_beiboots(crds):
    from tests.utils import create_beiboot_object

    create_beiboot_object(name="my-test-1", parameters={})
    create_beiboot_object(name="my-test-2", parameters={"maxLifetime": "2h"})

    runner = CliRunner()
    result = runner.invoke(
        list_clusters,  # noqa
        obj={"config": ClientConfiguration()},
    )
    assert result.exit_code == 0
