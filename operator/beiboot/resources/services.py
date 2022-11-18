import logging
from typing import List

import kubernetes as k8s

from beiboot.configuration import ClusterConfiguration

logger = logging.getLogger("beiboot")


def ports_to_services(
    ports: List[str], namespace: str, cluster_config: ClusterConfiguration
) -> List[k8s.client.V1Service]:
    services = []
    for port in ports:
        try:
            target = port.split(":")[1]
            iport = int(target)
        except ValueError:
            logger.error(
                f"Cannot create service for port {target}: could not parse to int."
            )
            continue
        except IndexError:
            logger.error(
                f"Cannot create service for port {target}: not in form <int>:<int>"
            )
            continue
        spec = k8s.client.V1ServiceSpec(
            type="ClusterIP",
            selector=cluster_config.nodeLabels,
            ports=[
                k8s.client.V1ServicePort(
                    name=f"{target}-tcp", target_port=iport, port=iport, protocol="TCP"
                ),
                k8s.client.V1ServicePort(
                    name=f"{target}-udp", target_port=iport, port=iport, protocol="UDP"
                ),
            ],
        )
        service = k8s.client.V1Service(
            api_version="v1",
            kind="Service",
            metadata=k8s.client.V1ObjectMeta(
                name=f"port-{target}", namespace=namespace
            ),
            spec=spec,
        )
        services.append(service)
    return services


def gefyra_service(port: int, namespace: str, cluster_config: ClusterConfiguration
) -> k8s.client.V1Service:
    """
    It creates a service that exposes the gefyra port on all nodes in the cluster

    :param port: The port number that the service will be exposed on
    :type port: int
    :param namespace: The namespace to deploy the service in
    :type namespace: str
    :param cluster_config: ClusterConfiguration
    :type cluster_config: ClusterConfiguration
    :return: A service object
    """
    spec = k8s.client.V1ServiceSpec(
        type="NodePort",
        selector=cluster_config.nodeLabels,
        ports=[
            k8s.client.V1ServicePort(
                name=f"{port}-gefyra",
                node_port=port,
                target_port=31820,
                port=31820,
                protocol="UDP",
            ),
        ],
    )
    service = k8s.client.V1Service(
        api_version="v1",
        kind="Service",
        metadata=k8s.client.V1ObjectMeta(name="gefyra-nodeport", namespace=namespace),
        spec=spec,
    )
    return service
