from beiboot.configuration import ClientConfiguration
from beiboot.connection.factory import connector_factory
from beiboot.connection.ghostunnel.docker import GhostunnelDocker
from beiboot.connection.types import ConnectorType


def test_ghostunnel_docker_unit():
    conn = connector_factory.get(
        connector_type=ConnectorType.GHOSTUNNEL_DOCKER,
        configuration=ClientConfiguration(),
    )
    assert type(conn) == GhostunnelDocker
