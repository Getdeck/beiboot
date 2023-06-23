from click.testing import CliRunner

from beiboot.configuration import ClientConfiguration
from cli.shelf import delete_shelf


def test_delete_no_shelf(minikube):
    runner = CliRunner()
    result = runner.invoke(
        delete_shelf,  # noqa
        ["shelf-test"],
        obj={"config": ClientConfiguration()},
    )
    assert result.exit_code == 1


def test_delete_shelf_object(crds):
    from tests.utils import create_beiboot_object, create_shelf_object

    create_beiboot_object(name="my-test-delete", parameters={})
    create_shelf_object(name="shelf-test-delete")

    runner = CliRunner()
    result = runner.invoke(
        delete_shelf,  # noqa
        ["shelf-test-delete"],
        obj={"config": ClientConfiguration()},
    )
    assert result.exit_code == 0


def test_delete_no_shelf_object(crds):

    runner = CliRunner()
    result = runner.invoke(
        delete_shelf,  # noqa
        ["shelf-test-delete1"],
        obj={"config": ClientConfiguration()},
    )
    assert result.exit_code == 1
