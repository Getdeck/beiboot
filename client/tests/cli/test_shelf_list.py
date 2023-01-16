from click.testing import CliRunner

from beiboot.configuration import ClientConfiguration
from cli.shelf import list_shelves


def test_list_no_beiboot(minikube):
    runner = CliRunner()
    result = runner.invoke(
        list_shelves,  # noqa
        obj={"config": ClientConfiguration()},
    )
    assert (
        result.stdout.strip()
        == "Error: This cluster does probably not support Getdeck Beiboot, or is not ready."
    )
    assert result.exit_code == 1


def test_list_empty(crds):
    runner = CliRunner()
    result = runner.invoke(
        list_shelves,  # noqa
        obj={"config": ClientConfiguration()},
    )
    assert result.exit_code == 0


def test_list_beiboots(crds):
    from tests.utils import create_beiboot_object, create_shelf_object

    create_beiboot_object(name="my-test-1", parameters={})
    create_shelf_object(name="shelf-test-1")
    create_shelf_object(name="shelf-test-2", labels={"mylabel": "1"})

    runner = CliRunner()
    result = runner.invoke(
        list_shelves,  # noqa
        ["--label", "mylabel=1"],
        obj={"config": ClientConfiguration()},
    )

    assert result.exit_code == 0
