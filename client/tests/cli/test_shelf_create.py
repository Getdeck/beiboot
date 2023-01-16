from click.testing import CliRunner

from beiboot import api
from beiboot.configuration import ClientConfiguration
from beiboot.types import ShelfState
from cli.shelf import create_shelf


def test_create_no_beiboot(minikube):
    runner = CliRunner()
    result = runner.invoke(
        create_shelf,  # noqa
        ["my-test"],
        obj={"config": ClientConfiguration()},
    )
    assert result.exit_code == 1


def test_a_create_shelf_object(crds):
    from tests.utils import create_beiboot_object

    create_beiboot_object(name="shelf-test", parameters={})

    runner = CliRunner()
    result = runner.invoke(
        create_shelf,  # noqa
        ["shelf-test"],
        obj={"config": ClientConfiguration()},
    )
    assert result.exit_code == 0
    assert not result.exception

    # shelf has auto-generated name
    shelf = api.read_all_shelves()[0]
    assert shelf.state == ShelfState.REQUESTED


def test_b_create_shelf_object(crds):
    runner = CliRunner()
    result = runner.invoke(
        create_shelf,  # noqa
        ["shelf-test", "--shelf-name", "my-shelf-test"],
        obj={"config": ClientConfiguration()},
    )
    assert result.exit_code == 0
    assert not result.exception

    # get shelf by shelf-name
    shelf = api.read_shelf("my-shelf-test")
    assert shelf.state == ShelfState.REQUESTED


def test_c_create_shelf_object(crds):
    runner = CliRunner()
    result = runner.invoke(
        create_shelf,  # noqa
        ["shelf-test", "--shelf-name", "my-shelf-test"],
        obj={"config": ClientConfiguration()},
    )
    assert result.exit_code == 1
