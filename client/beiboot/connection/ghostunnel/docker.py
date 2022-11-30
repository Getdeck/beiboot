import logging
from typing import Optional, List

import docker

from beiboot.configuration import ClientConfiguration
from beiboot.connection.abstract import AbstractConnector
from beiboot.connection.types import ConnectorType
from beiboot.types import Beiboot
from beiboot.utils import _list_containers_by_prefix

logger = logging.getLogger(__name__)


class GhostunnelDockerBuilder:
    def __init__(self):
        self._instances = {}

    def __call__(
        self,
        configuration: ClientConfiguration,
        beiboot: Beiboot,
        additional_ports: Optional[List[str]],
        **_ignored,
    ):
        instance = GhostunnelDocker(
            configuration=configuration,
            beiboot=beiboot,
            additional_ports=additional_ports,
        )
        return instance


class GhostunnelDocker(AbstractConnector):

    connector_type = ConnectorType.GHOSTUNNEL_DOCKER.value
    IMAGE = "ghostunnel/ghostunnel:v1.7.1"

    def __init__(
        self,
        configuration: ClientConfiguration,
        beiboot: Beiboot,
        additional_ports: Optional[List[str]],
    ):
        super(GhostunnelDocker, self).__init__(configuration, beiboot, additional_ports)
        self.CONTAINER_PREFIX = f"getdeck-beiboot-{self.beiboot.name}"

    def establish(self) -> None:
        if self.beiboot.tunnel is None:
            raise RuntimeError(
                "Connection data is not available, unable to establish connection"
            )

        ghostunnel = self.beiboot.tunnel["ghostunnel"]
        remote_ports = ghostunnel.get(
            "ports"
        )  # "endpoint": -> address; "target": cluster port

        def _nodeport_for_target(target: str) -> Optional[str]:
            for port in remote_ports:
                if str(port.get("target")) == target:
                    return port.get("endpoint")
            return None

        self.additional_ports.extend(self.beiboot.parameters.ports or [])
        mtls_files = self.save_mtls_files()  # {filename, path}
        for call_port in self.additional_ports:
            local_port, cluster_port = call_port.split(":")
            _endpoint = _nodeport_for_target(cluster_port)
            if not _endpoint:
                logger.warning(f"No endpoint for cluster port {cluster_port}")
                continue
            _cmd = (
                f"client --listen 0.0.0.0:{local_port} --unsafe-listen "
                f"--target {_endpoint} --cert /crt/client.crt --key /crt/client.key --cacert /crt/ca.crt"
            )
            try:
                container = self.configuration.DOCKER.containers.run(  # noqa
                    image=self.IMAGE,
                    name=f"{self.CONTAINER_PREFIX}-{cluster_port}",
                    command=_cmd,
                    restart_policy={"Name": "unless-stopped"},
                    remove=False,
                    detach=True,
                    ports={f"{local_port}": int(local_port)},
                    volumes=[
                        f"{path}:/crt/{file}" for file, path in mtls_files.items()
                    ],
                )
            except docker.errors.APIError as e:
                if e.status_code == 409:
                    continue
                else:
                    raise RuntimeError(
                        f"Could not run ghostunnel container due to the following error: {e}"
                    ) from None

    def terminate(self) -> None:
        try:
            containers = _list_containers_by_prefix(
                self.configuration, self.CONTAINER_PREFIX
            )
            for container in containers:
                try:
                    container.kill()  # type: ignore
                except:  # noqa
                    pass
                try:
                    container.remove()  # type: ignore
                except:  # noqa
                    pass
        except docker.errors.APIError as e:
            logger.warning(str(e))