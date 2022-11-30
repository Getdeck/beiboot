import logging

from beiboot.api.utils import stopwatch
from beiboot.configuration import default_configuration, ClientConfiguration
from beiboot.connection.abstract import AbstractConnector
from beiboot.connection.factory import connector_factory
from beiboot.connection.types import ConnectorType
from beiboot.types import Beiboot, BeibootProvider

logger = logging.getLogger(__name__)


def _get_connector(
    beiboot: Beiboot, connector_type: ConnectorType, config: ClientConfiguration
) -> AbstractConnector:
    additional_ports = []
    if BeibootProvider(beiboot.provider) == BeibootProvider.K3S:
        additional_ports = ["6443:6443"]

    connector = connector_factory.get(
        connector_type=connector_type,
        configuration=config,
        beiboot=beiboot,
        additional_ports=additional_ports,
    )
    return connector


@stopwatch
def connect(
    beiboot: Beiboot,
    connector_type: ConnectorType,
    config: ClientConfiguration = default_configuration,
) -> AbstractConnector:
    connector = _get_connector(beiboot, connector_type, config)
    connector.establish()
    return connector


@stopwatch
def terminate(
    beiboot: Beiboot,
    connector_type: ConnectorType,
    config: ClientConfiguration = default_configuration,
) -> AbstractConnector:
    connector = _get_connector(beiboot, connector_type, config)
    connector.terminate()
    return connector
