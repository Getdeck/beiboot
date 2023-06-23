import logging
from typing import Optional, List

from beiboot.api.utils import stopwatch
from beiboot.configuration import default_configuration, ClientConfiguration
from beiboot.connection.abstract import AbstractConnector
from beiboot.connection.factory import connector_factory
from beiboot.connection.types import ConnectorType
from beiboot.types import Beiboot

logger = logging.getLogger(__name__)


def _get_connector(
    connector_type: ConnectorType, config: ClientConfiguration
) -> AbstractConnector:
    connector = connector_factory.get(
        connector_type=connector_type,
        configuration=config,
    )
    return connector


@stopwatch
def connect(
    beiboot: Beiboot,
    connector_type: ConnectorType,
    host: Optional[str] = None,
    config: ClientConfiguration = default_configuration,
    _docker_network: Optional[str] = None,
) -> AbstractConnector:
    """
    Connects to a Beiboot instance.

    :param beiboot: The Beiboot instance to connect to.
    :type beiboot: Beiboot
    :param connector_type: The connector type to use.
    :type connector_type: ConnectorType
    :param host: The host to connect to.
    :param config: The client configuration to use.
    :type config: ClientConfiguration

    :return: A AbstractConnector instance
    """
    additional_ports: List = []
    connector = _get_connector(connector_type, config)

    if connector_type == ConnectorType.GHOSTUNNEL_DOCKER and _docker_network:
        # this is for local testing purposes
        connector.set_docker_network(_docker_network)  # type: ignore

    connector.establish(beiboot, additional_ports, host)
    return connector


@stopwatch
def terminate(
    name: str,  # passing only the name, as the Beiboot may already deleted
    connector_type: ConnectorType,
    config: ClientConfiguration = default_configuration,
) -> AbstractConnector:
    """
    Terminate a Beiboot connection and clean up

    :param name: The Beiboot instance name
    :type name: str
    :param connector_type: The connector type to use.
    :type connector_type: ConnectorType

    :return: A AbstractConnector instance
    """
    connector = _get_connector(connector_type, config)
    connector.terminate(name=name)
    connector.delete_beiboot_config_directory(beiboot_name=name)
    return connector
