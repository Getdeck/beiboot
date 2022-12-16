import logging
from typing import Optional, List

from beiboot.configuration import ClientConfiguration
from beiboot.connection.abstract import AbstractConnector
from beiboot.types import Beiboot

logger = logging.getLogger(__name__)


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

        def _nodeport_for_target(target: str) -> Optional[str]:
            for port in remote_ports:
                if str(port.get("target")) == target:
                    _host, _port = port.get("endpoint").split(":")
                    if (not bool(_host) or _host == "None") and not bool(host):
                        return "Unavailable"
                    return f"{host or _host}:{_port}"
            return None

        ghostunnel = beiboot.tunnel["ghostunnel"]  # type: ignore
        remote_ports = ghostunnel.get("ports")
        if not additional_ports:
            additional_ports = []
        for call_port in additional_ports:
            local_port, cluster_port = call_port.split(":")
            _endpoint = _nodeport_for_target(cluster_port)
            if not _endpoint:
                logger.warning(f"No endpoint for cluster port {cluster_port}")
                continue
            else:
                logger.info(f"Forwarding port: {local_port} -> {_endpoint}")

    def terminate(self, name: str) -> None:
        self.delete_beiboot_config_directory(name)
