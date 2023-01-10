from click.testing import CliRunner

from beiboot.configuration import ClientConfiguration
from cli.install import install, uninstall


def test_install_beiboot():
    runner = CliRunner()
    result = runner.invoke(
        install,  # noqa
        [
            "--component=configmap",
            "--server-requests-cpu=4",
            "--server-requests-memory=4Gi",
            "--node-requests-cpu=4",
            "--node-requests-memory=4Gi",
            "-o",
        ],
        obj={"config": ClientConfiguration()},
    )
    assert result.exit_code == 0

def test_uninstall_beiboot(operator):
    from tests.utils import create_beiboot_object

    create_beiboot_object(name="my-test-delete1", parameters={})

    runner = CliRunner()
    result = runner.invoke(
        uninstall,  # noqa
        ["-f"],
        obj={"config": ClientConfiguration()},
    )
    assert result.exit_code == 0
