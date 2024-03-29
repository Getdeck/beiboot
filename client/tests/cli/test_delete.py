from click.testing import CliRunner

from beiboot.configuration import ClientConfiguration
from cli.cluster import delete_cluster


def test_delete_no_beiboot(minikube):
    runner = CliRunner()
    result = runner.invoke(
        delete_cluster,  # noqa
        ["my-test"],
        obj={"config": ClientConfiguration()},
    )
    assert result.exit_code == 1


def test_delete_beiboot_object(crds):
    from tests.utils import create_beiboot_object

    create_beiboot_object(name="my-test-delete", parameters={})

    runner = CliRunner()
    result = runner.invoke(
        delete_cluster,  # noqa
        ["my-test-delete"],
        obj={"config": ClientConfiguration()},
    )
    assert result.exit_code == 0


def test_delete_no_beiboot_object(crds):

    runner = CliRunner()
    result = runner.invoke(
        delete_cluster,  # noqa
        ["my-test-delete1"],
        obj={"config": ClientConfiguration()},
    )
    assert result.exit_code == 1
