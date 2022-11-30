import shutil
from typing import Optional, List

from beiboot.configuration import ClientConfiguration
from beiboot.connection.abstract import AbstractConnector
from beiboot.connection.types import ConnectorType
from beiboot.types import Beiboot


class GhostunnelNativeBuilder:
    def __init__(self):
        self._instances = {}

    def __call__(
        self,
        configuration: ClientConfiguration,
        beiboot: Beiboot,
        additional_ports: Optional[List[str]],
        **_ignored,
    ):
        instance = GhostunnelNative(
            configuration=configuration,
            beiboot=beiboot,
            additional_ports=additional_ports,
        )
        return instance


class GhostunnelNative(AbstractConnector):

    connector_type = ConnectorType.GHOSTUNNEL_NATIVE.value

    def establish(self) -> None:
        if not shutil.which("ghostunnel"):
            raise RuntimeError(
                "The ghostunnel executable is not installed on this machine. "
                "Please get it from here: https://github.com/ghostunnel/ghostunnel/releases"
            )

    def terminate(self) -> None:
        pass
