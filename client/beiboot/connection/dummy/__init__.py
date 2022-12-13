from typing import Optional, List

from beiboot.configuration import ClientConfiguration
from beiboot.connection.abstract import AbstractConnector
from beiboot.types import Beiboot


class DummyNoConnectBuilder:
    def __init__(self):
        self._instances = {}

    def __call__(
        self,
        configuration: ClientConfiguration,
        **_ignored,
    ):
        instance = DummyNoConnect(
            configuration=configuration,
        )
        return instance


class DummyNoConnect(AbstractConnector):
    def establish(
        self,
        beiboot: Beiboot,
        additional_ports: Optional[List[str]],
        host: Optional[str],
    ) -> None:
        _ = self.save_mtls_files(beiboot)
        _ = self.save_serviceaccount_files(beiboot)

    def terminate(self, name: str) -> None:
        self.delete_beiboot_config_directory(name)
