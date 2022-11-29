import logging

from beiboot.configuration import default_configuration, ClientConfiguration

logger = logging.getLogger(__name__)


def write_mtls_files(
    location: str, config: ClientConfiguration = default_configuration
):
    pass


def write_serviceaccount_files(
    location: str, config: ClientConfiguration = default_configuration
):
    pass
