import shutil
import tempfile
from pathlib import Path

from beiboot import api
from beiboot.configuration import ClientConfiguration
from beiboot.connection.abstract import AbstractConnector
from beiboot.types import BeibootParameters, BeibootRequest, BeibootState


def test_write_files(operator, timeout):
    req = BeibootRequest(
        name="mycluster",
        parameters=BeibootParameters(
            nodes=1,
            serverStorageRequests="500Mi",
            serverResources={"requests": {"cpu": "0.5", "memory": "0.5Gi"}},
            nodeResources={"requests": {"cpu": "0.5", "memory": "0.5Gi"}},
        ),
    )
    bbt = api.create(req)
    bbt.wait_for_state(awaited_state=BeibootState.READY, timeout=timeout)

    dirpath = tempfile.mkdtemp()
    config = ClientConfiguration(getdeck_config_root=dirpath)

    class TestConnector(AbstractConnector):
        def establish(self) -> None:
            pass

        def terminate(self) -> None:
            pass

    ac = TestConnector(config)
    files = ac.save_mtls_files(bbt)
    for _, location in files.items():
        assert Path(location).is_file() is True

    files = ac.save_serviceaccount_files(bbt)
    for _, location in files.items():
        assert Path(location).is_file() is True

    shutil.rmtree(dirpath)
