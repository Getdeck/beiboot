import sys
import logging
from pathlib import Path
from typing import Optional, Union

console = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("[%(levelname)s] %(message)s")
console.setFormatter(formatter)

logger = logging.getLogger(__name__)
logger.addHandler(console)

__VERSION__ = "1.4.0"


class ClientConfiguration(object):
    def __init__(
        self,
        getdeck_config_root: Optional[Union[str, Path]] = None,
        docker_client=None,
        namespace: str = "getdeck",
        registry_url: Optional[str] = None,
        tooler_image: Optional[str] = None,
        cluster_timeout: int = 180,
    ):
        self.NAMESPACE = namespace
        self.CONFIGMAP_NAME = "beiboot-config"
        self.CLIENT_HEARTBEAT_CONFIGMAP_NAME = "beiboot-clients"
        self.REGISTRY_URL = (
            registry_url.rstrip("/") if registry_url else "quay.io/getdeck"
        )
        if registry_url:
            logger.debug(
                f"Using registry prefix (other than default): {self.REGISTRY_URL}"
            )
        self.TOOLER_IMAGE = (
            # tooler_image or f"{self.REGISTRY_URL}/tooler:{__VERSION__}"
            tooler_image
            or f"{self.REGISTRY_URL}/tooler:latest"
        )
        if tooler_image:
            logger.debug(f"Using Tooler image (other than default): {tooler_image}")

        if docker_client:
            self.DOCKER = docker_client

        self.CLUSTER_CREATION_TIMEOUT = (
            cluster_timeout  # cluster timeout for the kubeconfig
        )
        if not getdeck_config_root:
            self.KUBECONFIG_LOCATION = Path.home().joinpath(".getdeck")
        else:
            self.KUBECONFIG_LOCATION = Path(getdeck_config_root)

    def _init_docker(self):
        import docker

        try:
            self.DOCKER = docker.from_env()
        except docker.errors.DockerException as de:
            logger.fatal(f"Docker init error: {de}")
            raise docker.errors.DockerException(
                "Docker init error. Docker host not running?"
            )

    def _init_kubeapi(self):
        from kubernetes.client import (
            CoreV1Api,
            RbacAuthorizationV1Api,
            AppsV1Api,
            CustomObjectsApi,
            ApiextensionsV1Api,
            AdmissionregistrationV1Api,
        )

        self.K8S_CORE_API = CoreV1Api()
        self.K8S_RBAC_API = RbacAuthorizationV1Api()
        self.K8S_APP_API = AppsV1Api()
        self.K8S_CUSTOM_OBJECT_API = CustomObjectsApi()
        self.K8S_EXTENSIONS_API = ApiextensionsV1Api()
        self.K8S_ADMISSION_API = AdmissionregistrationV1Api()

    def __getattr__(self, item):
        if item in [
            "K8S_CORE_API",
            "K8S_RBAC_API",
            "K8S_APP_API",
            "K8S_CUSTOM_OBJECT_API",
            "K8S_ADMISSION_API",
            "K8S_EXTENSIONS_API",
        ]:
            try:
                return self.__getattribute__(item)
            except AttributeError:
                self._init_kubeapi()
        if item == "DOCKER":
            try:
                return self.__getattribute__(item)
            except AttributeError:
                self._init_docker()

        return self.__getattribute__(item)

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if k.isupper()}

    def __str__(self):
        return str(self.to_dict())


default_configuration = ClientConfiguration()
