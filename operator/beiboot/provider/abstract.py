from abc import ABC, abstractmethod
from typing import List, Optional, Dict


class AbstractClusterProvider(ABC):
    provider_type = ""

    def __init__(self, name: str, namespace: str, ports: Optional[List[str]], shelf_name: str = None) -> None:
        self.name = name
        self.namespace = namespace
        self.ports = ports
        self.shelf_name = shelf_name

    @abstractmethod
    async def get_kubeconfig(self) -> str:
        """
        Extract the kubeconfig for this Beiboot cluster
        """
        raise NotImplementedError

    # @abstractmethod
    # async def create(self) -> bool:
    #     """
    #     Create the workloads for the Beiboot cluster and apply them, return the result
    #     """
    #     raise NotImplementedError

    async def create(self) -> bool:
        """
        Create the workloads for the Beiboot cluster and apply them, return the result
        """
        if self.shelf_name:
            await self.restore_from_shelf()
        else:
            await self.create_new()

    @abstractmethod
    async def create_new(self) -> bool:
        """
        Create the workloads for the Beiboot cluster and apply them, return the result
        """
        raise NotImplementedError

    @abstractmethod
    async def restore_from_shelf(self) -> bool:
        """
        Restore the persistent volumes from the Shelf and create the workloads as persisted in the Shelf for the
        Beiboot cluster and apply them, return the result
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

    def get_ports(self) -> Optional[List[str]]:
        """
        Return the published ports
        """
        return self.ports

    async def get_pvc_mapping(self) -> Dict:
        """
        Return a mapping of node-names to the PVC that node uses.
        """
        raise NotImplementedError
