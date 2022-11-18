from abc import ABC, abstractmethod
from typing import List


class AbstractClusterProvider(ABC):
    provider_type = None

    def __init__(self, name: str, namespace: str, ports: List[str]) -> None:
        self.name = name
        self.namespace = namespace
        self.ports = ports

    @abstractmethod
    async def get_kubeconfig(self) -> str:
        """
        Extract the kubeconfig for this Beiboot cluster
        """
        raise NotImplementedError

    @abstractmethod
    async def create(self) -> bool:
        """
        Create the workloads for the Beiboot cluster and apply them, return the result
        """
        raise NotImplementedError

    @abstractmethod
    async def delete(self) -> bool:
        """
        Delete the Beiboot cluster and return the result
        """
        raise NotImplementedError

    @abstractmethod
    async def exists(self) -> bool:
        """
        Returns True if the Beiboot cluster exists, otherwise False
        """
        raise NotImplementedError

    @abstractmethod
    async def running(self) -> bool:
        """
        Returns True if the Beiboot cluster is running, otherwise False
        """
        raise NotImplementedError

    @abstractmethod
    async def ready(self) -> bool:
        """
        Returns True if the Beiboot cluster is ready to accept workloads, otherwise False
        """
        raise NotImplementedError

    @abstractmethod
    def api_version(self) -> str:
        """
        Best return a type that allows working comparisons between versions of the same provider.
        E.g. (1, 10) > (1, 2), but "1.10" < "1.2"
        """
        raise NotImplementedError

    def get_ports(self) -> List[str]:
        """
        Return the published ports
        """
        return self.ports
