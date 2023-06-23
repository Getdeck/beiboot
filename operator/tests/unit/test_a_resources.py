import logging
from time import sleep

import pytest

from beiboot.configuration import ClusterConfiguration
from beiboot.resources.configmaps import create_beiboot_configmap
from beiboot.resources.services import ports_to_services


from tests.utils import demo_statefulset, demo_service, demo_deployment


def test_ports_to_service():
    config = ClusterConfiguration()
    services = ports_to_services(
        ports=["8080:80", "8443:443"], namespace="test-namespace", cluster_config=config
    )
    assert len(services) == 2
    services = ports_to_services(
        ports=["8080:80", "8443"], namespace="test-namespace", cluster_config=config
    )
    assert len(services) == 1
    services = ports_to_services(
        ports=["8080:80", "8443:uint"],
        namespace="test-namespace",
        cluster_config=config,
    )
    assert len(services) == 1
    services = ports_to_services(
        ports=["ss080:80", "8443:443"],
        namespace="test-namespace",
        cluster_config=config,
    )
    assert len(services) == 2

    svc = services[0]
    assert svc.metadata.name == "port-80"
    assert len(svc.spec.ports) == 2
    assert svc.spec.ports[0].name == "80-tcp"
    assert svc.spec.ports[1].name == "80-udp"


def test_beiboot_configmap():
    configmap = create_beiboot_configmap(
        ClusterConfiguration().encode_cluster_configuration()
    )
    # these are the default Beiboot parameters
    assert configmap.data["clusterReadyTimeout"] == "180"
    assert configmap.data["nodes"] == "1"
    assert configmap.metadata.name == "beiboot-config"


class TestResources:
    def test_create_statefulset(self, minikube):
        from beiboot.resources.utils import handle_create_statefulset

        sts = demo_statefulset()
        handle_create_statefulset(logging.getLogger(), sts, "default")
        handle_create_statefulset(logging.getLogger(), sts, "default")

    def test_delete_statefulset(self, minikube):
        from beiboot.resources.utils import handle_delete_statefulset

        sts = demo_statefulset()
        handle_delete_statefulset(logging.getLogger(), sts.metadata.name, "default")
        handle_delete_statefulset(logging.getLogger(), sts.metadata.name, "default")

    def test_create_deployment(self, minikube):
        from beiboot.resources.utils import handle_create_deployment

        deploy = demo_deployment()
        handle_create_deployment(logging.getLogger(), deploy, "default")
        handle_create_deployment(logging.getLogger(), deploy, "default")

    def test_create_namespace(self, minikube):
        from beiboot.resources.utils import handle_create_namespace

        handle_create_namespace(logging.getLogger(), "my-namespace")
        handle_create_namespace(logging.getLogger(), "my-namespace")

    def test_create_service(self, minikube):
        from beiboot.resources.utils import handle_create_service

        svc = demo_service()
        handle_create_service(logging.getLogger(), svc, "default")
        handle_create_service(logging.getLogger(), svc, "default")

    def test_delete_service(self, minikube):
        from beiboot.resources.utils import handle_delete_service

        svc = demo_service()
        handle_delete_service(logging.getLogger(), svc.metadata.name, "default")
        handle_delete_service(logging.getLogger(), svc.metadata.name, "default")

    @pytest.mark.asyncio
    async def test_delete_namespace(self, minikube):
        from beiboot.resources.utils import handle_delete_namespace

        await handle_delete_namespace(logging.getLogger(), "my-namespace")
        await handle_delete_namespace(logging.getLogger(), "my-namespace")

    @pytest.mark.asyncio
    async def test_service_account(self, minikube):
        import kubernetes
        import kopf
        from beiboot.resources.utils import (
            handle_create_beiboot_serviceaccount,
            get_serviceaccount_data,
        )

        handle_create_beiboot_serviceaccount(logging.getLogger(), "beiboot", "default")
        with pytest.raises(kubernetes.client.exceptions.ApiException):
            handle_create_beiboot_serviceaccount(
                logging.getLogger(), "beiboot", "default"
            )
        with pytest.raises(kopf.TemporaryError):
            await get_serviceaccount_data("beiboot", "default")
        sleep(2)
        sa = await get_serviceaccount_data("beiboot", "default")
        assert type(sa) == dict
