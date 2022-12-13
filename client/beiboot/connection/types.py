from enum import Enum


class ConnectorType(Enum):
    GHOSTUNNEL_DOCKER = "ghostunnel_docker"
    DUMMY_NO_CONNECT = "dummy_no_connect"
