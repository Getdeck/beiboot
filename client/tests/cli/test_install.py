from click.testing import CliRunner

from beiboot.configuration import ClientConfiguration
from cli.install import install


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
        ],
        obj={"config": ClientConfiguration()},
    )
    assert result.exit_code == 0
