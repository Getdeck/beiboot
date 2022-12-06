import os.path
import pathlib
import shutil
from abc import ABC, abstractmethod
from typing import Optional, List, Iterable

from beiboot.configuration import ClientConfiguration
from beiboot.connection.utils import compose_kubeconfig_for_serviceaccount
from beiboot.types import Beiboot
from beiboot.utils import get_kubeconfig_location, get_beiboot_config_location


class AbstractConnector(ABC):
    connector_type = ""
    beiboot: Beiboot
    additional_ports: Optional[List[str]]

    def __init__(
        self,
        configuration: ClientConfiguration,
    ) -> None:
        self.configuration = configuration

    @abstractmethod
    def establish(
        self,
        beiboot: Beiboot,
        additional_ports: Optional[List[str]],
        host: Optional[str],
    ) -> None:
        """
        Establishes a connection to a Beiboot

        :param beiboot: The Beiboot object that is being used to establish the connection
        :type beiboot: Beiboot
        :param additional_ports: A list of ports that should be forwarded to the host
        :type additional_ports: Optional[List[str]]
        :param host: The hostname or IP address of the host to connect to
        :type host: Optional[str]
        """
        raise NotImplementedError

    @abstractmethod
    def terminate(self, name: str) -> None:
        """
        Terminate the connection, clean up

        :param name: The name of the process to terminate
        :type name: str
        """
        raise NotImplementedError

    def _save_items(
        self, beiboot_name: str, items: Iterable, prefix: str = "."
    ) -> dict[str, str]:
        location = os.path.join(
            get_beiboot_config_location(self.configuration, beiboot_name), prefix
        )
        pathlib.Path(location).mkdir(parents=True, exist_ok=True)
        file_locations = {}
        for fname, content in items:
            _p = str(pathlib.Path(location).joinpath(fname))
            file_locations[fname] = _p
            with open(_p, "w") as f:
                f.write(content)
        return file_locations

    def save_mtls_files(self, beiboot: Beiboot) -> dict[str, str]:
        _mtls_files = beiboot.mtls_files
        if not _mtls_files:
            raise RuntimeError("Cannot write mTLS files")
        return self._save_items(beiboot.name, _mtls_files.items(), "mtls")

    def save_serviceaccount_files(self, beiboot: Beiboot) -> dict[str, str]:
        _sa_tokens = beiboot.serviceaccount_tokens
        if not _sa_tokens:
            raise RuntimeError("Cannot write Service account files")
        sa_files = self._save_items(beiboot.name, _sa_tokens.items(), "serviceaccount")
        location = get_beiboot_config_location(self.configuration, beiboot.name)
        try:
            import kubernetes as k8s

            api_host = k8s.client.api_client.ApiClient().configuration.host
            sa_kubeconfig = str(pathlib.Path(location).joinpath("sa_kubeconfig.yaml"))
            with open(sa_kubeconfig, "w") as f:
                f.write(
                    compose_kubeconfig_for_serviceaccount(
                        api_host,
                        _sa_tokens["ca.crt"],
                        _sa_tokens["namespace"],
                        _sa_tokens["token"],
                    )
                )
            sa_files.update({"sa_kubeconfig.yaml": sa_kubeconfig})
        except Exception as e:
            print(e)
        return sa_files

    def save_kubeconfig_to_file(self, beiboot: Beiboot) -> str:
        _kubeconfig = beiboot.kubeconfig
        if not _kubeconfig:
            raise RuntimeError("Cannot write kubeconfig")
        location = get_kubeconfig_location(self.configuration, beiboot.name)
        with open(location, "w") as yaml_file:
            yaml_file.write(_kubeconfig)
        return location

    def delete_kubeconfig_file(self, beiboot_name: str):
        location = get_kubeconfig_location(self.configuration, beiboot_name)
        pathlib.Path(location).unlink(missing_ok=True)

    def delete_beiboot_config_directory(self, beiboot_name):
        location = get_beiboot_config_location(self.configuration, beiboot_name)
        shutil.rmtree(location, ignore_errors=True)
