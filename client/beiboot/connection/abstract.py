import pathlib
import shutil
from abc import ABC, abstractmethod
from typing import Optional, List, Iterable

from beiboot.configuration import ClientConfiguration
from beiboot.types import Beiboot
from beiboot.utils import get_kubeconfig_location, get_beiboot_config_location


class AbstractConnector(ABC):
    connector_type = ""

    def __init__(
        self,
        configuration: ClientConfiguration,
        beiboot: Beiboot,
        additional_ports: Optional[List[str]],
    ) -> None:
        self.configuration = configuration
        self.beiboot = beiboot
        self.additional_ports = additional_ports or []

    @abstractmethod
    def establish(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def terminate(self) -> None:
        raise NotImplementedError

    def _save_items(self, items: Iterable) -> dict[str, str]:
        location = get_beiboot_config_location(self.configuration, self.beiboot.name)
        file_locations = {}
        for fname, content in items:
            _p = str(pathlib.Path(location).joinpath(fname))
            file_locations[fname] = _p
            with open(_p, "w") as f:
                f.write(content)
        return file_locations

    def save_mtls_files(self) -> dict[str, str]:
        _mtls_files = self.beiboot.mtls_files
        if not _mtls_files:
            raise RuntimeError("Cannot write mTLS files")
        return self._save_items(_mtls_files.items())

    def save_serviceaccount_files(self) -> dict[str, str]:
        _sa_tokens = self.beiboot.serviceaccount_tokens
        if not _sa_tokens:
            raise RuntimeError("Cannot write Service account files")
        return self._save_items(_sa_tokens.items())

    def save_kubeconfig_to_file(self) -> str:
        _kubeconfig = self.beiboot.kubeconfig
        if not _kubeconfig:
            raise RuntimeError("Cannot write kubeconfig")
        location = get_kubeconfig_location(self.configuration, self.beiboot.name)
        with open(location, "w") as yaml_file:
            yaml_file.write(_kubeconfig)
        return location

    def delete_kubeconfig_file(self):
        location = get_kubeconfig_location(self.configuration, self.beiboot.name)
        pathlib.Path(location).unlink(missing_ok=True)

    def delete_beiboot_config_directory(self):
        location = get_beiboot_config_location(self.configuration, self.beiboot.name)
        shutil.rmtree(location, ignore_errors=True)
