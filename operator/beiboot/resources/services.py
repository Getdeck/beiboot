import logging
from typing import List

import kubernetes as k8s

logger = logging.getLogger("beiboot")


def ports_to_services(ports: List[str], namespace: str) -> List[k8s.client.V1Service]:
    services = []
    for port in ports:
        try:
            target = port.split(":")[1]
            iport = int(target)
        except ValueError:
            logger.error(f"Cannot create service for port {target}: could not parse to int.")
            continue
        except IndexError:
            logger.error(f"Cannot create service for port {target}: not in form <int>:<int>")
            continue
        spec = k8s.client.V1ServiceSpec(
            type="ClusterIP",
            selector={"app": "agent"},
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
            metadata=k8s.client.V1ObjectMeta(name=f"port-{target}", namespace=namespace),
            spec=spec,
        )
        services.append(service)
    return services
