import getpass
import logging
import socket
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
        **_ignored,
    ):
        instance = GhostunnelDocker(
            configuration=configuration,
        )
        return instance


class GhostunnelDocker(AbstractConnector):

    connector_type = ConnectorType.GHOSTUNNEL_DOCKER.value
    IMAGE = "ghostunnel/ghostunnel:v1.7.1"
    HEARTBEAT_IMAGE = "quay.io/getdeck/tooler:latest"
    CONTAINER_PREFIX = "getdeck-beiboot-{name}"
    _DOCKER_NETWORK_NAME = None
    HEARTBEAT_CMD = 'watch -n30 "VAR=\'{{\\"data\\":{{\\"{client}\\": \\"\'$(date +\\"%Y-%m-%dT%H:%M:%S\\")\'\\"}}}}\';  kubectl --kubeconfig /kubernetes/sa_kubeconfig.yaml patch configmap beiboot-clients -n {namespace} --type merge --patch=\\"$VAR\\""'  # noqa
    CLIENT = f"{socket.gethostname()}-{getpass.getuser()}"

    def __init__(
        self,
        configuration: ClientConfiguration,
    ):
        super(GhostunnelDocker, self).__init__(configuration)
        self.HEARTBEAT_IMAGE = configuration.TOOLER_IMAGE

    def set_docker_network(self, network_name):
        self._DOCKER_NETWORK_NAME = network_name

    def establish(
        self,
        beiboot: Beiboot,
        additional_ports: Optional[List[str]],
        host: Optional[str],
    ) -> None:
        if not additional_ports:
            additional_ports = []
        if beiboot.tunnel is None:
            raise RuntimeError(
                "Connection data is not available, unable to establish connection"
            )

        ghostunnel = beiboot.tunnel["ghostunnel"]
        remote_ports = ghostunnel.get(
            "ports"
        )  # "endpoint": -> address; "target": cluster port

        def _nodeport_for_target(target: str) -> Optional[str]:
            for port in remote_ports:
                if str(port.get("target")) == target:
                    _host, _port = port.get("endpoint").split(":")
                    if (not bool(_host) or _host == "None") and not bool(host):
                        raise RuntimeError(
                            "Cannot connect to this Beiboot, as there is no endpoint available."
                        )
                    return f"{host or _host}:{_port}"
            return None

        additional_ports.extend(beiboot.parameters.ports or [])
        mtls_files = self.save_mtls_files(beiboot)  # {filename, path}
        serviceaccount_files = self.save_serviceaccount_files(
            beiboot
        )  # {filename, path}
        container_prefixes = self.CONTAINER_PREFIX.format(name=beiboot.name)

        for call_port in additional_ports:
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
                    name=f"{container_prefixes}-{cluster_port}",
                    command=_cmd,
                    restart_policy={"Name": "unless-stopped"},
                    remove=False,
                    detach=True,
                    ports={f"{local_port}": int(local_port)},
                    volumes=[
                        f"{path}:/crt/{file}" for file, path in mtls_files.items()
                    ],
                    network=self._DOCKER_NETWORK_NAME or None,
                )
            except docker.errors.APIError as e:
                logger.critical(e)
                raise RuntimeError(
                    f"Could not run ghostunnel container due to the following error: {e}"
                ) from None

        try:

            container = self.configuration.DOCKER.containers.run(  # noqa
                image=self.HEARTBEAT_IMAGE,
                name=f"{container_prefixes}-heartbeat",
                command=self.HEARTBEAT_CMD.format(
                    client=self.CLIENT, namespace=beiboot.namespace
                ),
                restart_policy={"Name": "unless-stopped"},
                remove=False,
                detach=True,
                volumes=[
                    f"{path}:/kubernetes/{file}"
                    for file, path in serviceaccount_files.items()
                ],
                network=self._DOCKER_NETWORK_NAME or None,
            )
        except docker.errors.APIError as e:
            raise RuntimeError(
                f"Could not run heartbeat container due to the following error: {e}"
            ) from None

    def terminate(self, name: str) -> None:
        try:
            containers = _list_containers_by_prefix(
                self.configuration, self.CONTAINER_PREFIX.format(name=name)
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
