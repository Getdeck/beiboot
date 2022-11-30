from typing import Optional, List

from beiboot.configuration import ClientConfiguration
from beiboot.connection.abstract import AbstractConnector
from beiboot.connection.ghostunnel import (
    GhostunnelDockerBuilder,
)
from beiboot.connection.types import ConnectorType
from beiboot.types import Beiboot


class ConnectorFactory:
    def __init__(self):
        self._builders = {}

    def register_builder(self, connector_type: ConnectorType, builder):
        self._builders[connector_type.value] = builder

    def __create(
        self,
        connector_type: ConnectorType,
        configuration: ClientConfiguration,
        beiboot: Beiboot,
        additional_ports: Optional[List[str]],
        **kwargs
    ):
        builder = self._builders.get(connector_type.value)
        if not builder:
            raise ValueError(connector_type)
        return builder(configuration, beiboot, additional_ports, **kwargs)

    def get(
        self,
        connector_type: ConnectorType,
        configuration: ClientConfiguration,
        beiboot: Beiboot,
        additional_ports: Optional[List[str]],
        **kwargs
    ) -> AbstractConnector:
        return self.__create(
            connector_type, configuration, beiboot, additional_ports, **kwargs
        )


connector_factory = ConnectorFactory()
connector_factory.register_builder(
    ConnectorType.GHOSTUNNEL_DOCKER, GhostunnelDockerBuilder()
)
