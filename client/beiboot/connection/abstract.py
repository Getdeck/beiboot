import pathlib
import shutil
from abc import ABC, abstractmethod
from typing import Optional, List, Iterable

from beiboot.configuration import ClientConfiguration
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
        self, beiboot: Beiboot, additional_ports: Optional[List[str]]
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def terminate(self, name: str) -> None:
        raise NotImplementedError

    def _save_items(self, beiboot_name: str, items: Iterable) -> dict[str, str]:
        location = get_beiboot_config_location(self.configuration, beiboot_name)
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
        return self._save_items(beiboot.name, _mtls_files.items())

    def save_serviceaccount_files(self, beiboot: Beiboot) -> dict[str, str]:
        _sa_tokens = beiboot.serviceaccount_tokens
        if not _sa_tokens:
            raise RuntimeError("Cannot write Service account files")
        return self._save_items(beiboot.name, _sa_tokens.items())

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
