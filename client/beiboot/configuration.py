import sys
import os
import logging
from pathlib import Path
from typing import Optional

console = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("[%(levelname)s] %(message)s")
console.setFormatter(formatter)

logger = logging.getLogger("getdeck.beiboot")
logger.addHandler(console)

__VERSION__ = "1.0.0"


class ClientConfiguration(object):
    def __init__(
        self,
        docker_client=None,
        namespace: str = "getdeck",
        registry_url: Optional[str] = None,
        tooler_image: Optional[str] = None,
        cluster_timeout: int = 180,
        api_connection_timeout: int = 30,
        api_port: int = 6443,
        kube_config_file: Optional[str] = None,
        kube_context: Optional[str] = None,
        aws_dir: Optional[str] = None,
    ):
        self.NAMESPACE = namespace
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

        self.KUBECONFIG_FILE = kube_config_file
        self.AWS_DIR = aws_dir or os.path.expanduser("~/.aws")
        self.CLUSTER_CREATION_TIMEOUT = (
            cluster_timeout  # cluster timeout for the kubeconfig
        )
        self.CONNECTION_TIMEOUT = (
            api_connection_timeout  # timeout for the API connection
        )
        self.KUBECONFIG_LOCATION = Path.home().joinpath(".getdeck")
        self.KUBECONFIG_LOCATION.mkdir(parents=True, exist_ok=True)
        self.BEIBOOT_API_PORT = api_port
        self.context = kube_context or None

    def _init_docker(self):
        import docker

        try:
            self.DOCKER = docker.from_env()
        except docker.errors.DockerException as de:
            logger.fatal(f"Docker init error: {de}")
            raise docker.errors.DockerException(
                "Docker init error. Docker host not running?"
            )

    def _init_kubeapi(self, context=None):
        from kubernetes.client import (
            CoreV1Api,
            RbacAuthorizationV1Api,
            AppsV1Api,
            CustomObjectsApi,
        )
        from kubernetes.config import load_kube_config, config_exception

        try:
            if self.KUBECONFIG_FILE:
                load_kube_config(self.KUBECONFIG_FILE, context=context or self.context)
            else:
                load_kube_config(context=context or self.context)
        except config_exception.ConfigException as e:
            raise RuntimeError(f"Could not load kubeconfig or context: {e}") from None
        self.K8S_CORE_API = CoreV1Api()
        self.K8S_RBAC_API = RbacAuthorizationV1Api()
        self.K8S_APP_API = AppsV1Api()
        self.K8S_CUSTOM_OBJECT_API = CustomObjectsApi()

    def __getattr__(self, item):
        if item in [
            "K8S_CORE_API",
            "K8S_RBAC_API",
            "K8S_APP_API",
            "K8S_CUSTOM_OBJECT_API",
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
