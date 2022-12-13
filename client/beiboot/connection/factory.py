from beiboot.configuration import ClientConfiguration
from beiboot.connection.abstract import AbstractConnector
from beiboot.connection.dummy import DummyNoConnectBuilder
from beiboot.connection.ghostunnel import (
    GhostunnelDockerBuilder,
)
from beiboot.connection.types import ConnectorType


class ConnectorFactory:
    def __init__(self):
        self._builders = {}

    def register_builder(self, connector_type: ConnectorType, builder):
        self._builders[connector_type.value] = builder

    def __create(
        self,
        connector_type: ConnectorType,
        configuration: ClientConfiguration,
        **kwargs
    ):
        builder = self._builders.get(connector_type.value)
        if not builder:
            raise ValueError(connector_type)
        return builder(configuration, **kwargs)

    def get(
        self,
        connector_type: ConnectorType,
        configuration: ClientConfiguration,
        **kwargs
    ) -> AbstractConnector:
        return self.__create(connector_type, configuration, **kwargs)


connector_factory = ConnectorFactory()
connector_factory.register_builder(
    ConnectorType.GHOSTUNNEL_DOCKER, GhostunnelDockerBuilder()
)
connector_factory.register_builder(
    ConnectorType.DUMMY_NO_CONNECT, DummyNoConnectBuilder()
)
