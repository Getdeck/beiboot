from enum import Enum
from typing import List, Optional

from beiboot.configuration import BeibootConfiguration, ClusterConfiguration
from beiboot.provider.abstract import AbstractClusterProvider
from beiboot.provider.k3s import K3sBuilder


class ProviderType(Enum):
    K3S = "k3s"


class ClusterFactory:
    def __init__(self):
        self._builders = {}

    def register_builder(self, provider_type: ProviderType, builder):
        self._builders[provider_type.value] = builder

    def __create(
        self,
        provider_type: ProviderType,
        configuration: BeibootConfiguration,
        cluster_parameter: ClusterConfiguration,
        name: str,
        namespace: str,
        ports: Optional[List[str]],
        logger,
        shelf_name,
        **kwargs
    ):
        builder = self._builders.get(provider_type.value)
        if not builder:
            raise ValueError(provider_type)
        return builder(
            configuration, cluster_parameter, name, namespace, ports, logger, shelf_name, **kwargs
        )

    def get(
        self,
        provider_type: ProviderType,
        configuration: BeibootConfiguration,
        cluster_parameter: ClusterConfiguration,
        name: str,
        namespace: str,
        ports: Optional[List[str]],
        logger,
        shelf_name: str = None,
        **kwargs
    ) -> AbstractClusterProvider:
        return self.__create(
            provider_type,
            configuration,
            cluster_parameter,
            name,
            namespace,
            ports,
            logger,
            shelf_name,
            **kwargs
        )


cluster_factory = ClusterFactory()
cluster_factory.register_builder(ProviderType.K3S, K3sBuilder())
