from typing import Callable

import pytest

from beiboot import api
from beiboot.connection.types import ConnectorType
from beiboot.types import BeibootRequest, BeibootParameters, BeibootState, TunnelParams


class EnsureBeibootMixin:
    @staticmethod
    def _ensure_beiboot(name, minikube_ip, timeout):
        try:
            bbt = api.read(name)
        except RuntimeError:
            if minikube_ip:
                params = BeibootParameters(
                    nodes=1,
                    serverStorageRequests="100Mi",
                    serverResources={"requests": {"cpu": "0.25", "memory": "0.25Gi"}},
                    nodeResources={"requests": {"cpu": "0.25", "memory": "0.25Gi"}},
                    tunnel=TunnelParams(endpoint=minikube_ip),
                )
            else:
                params = BeibootParameters(
                    nodes=1,
                    serverStorageRequests="100Mi",
                    serverResources={"requests": {"cpu": "0.25", "memory": "0.25Gi"}},
                    nodeResources={"requests": {"cpu": "0.25", "memory": "0.25Gi"}},
                )
            bbt = api.create(
                BeibootRequest(
                    name=name,
                    parameters=params,
                )
            )
            with pytest.raises(RuntimeError):
                _ = api.connect(bbt, ConnectorType.GHOSTUNNEL_DOCKER)
            bbt.wait_for_state(awaited_state=BeibootState.READY, timeout=timeout)
        return bbt


class TestClientBase:

    beiboot_name = ""

    def get_target_namespace(self):
        # this mimics the default namespace pattern from the operator
        namespace = f"getdeck-bbt-{self.beiboot_name}"
        return namespace

    def _get_beiboot_data(self, kubectl: Callable) -> dict:
        try:
            output = kubectl(["-n", "getdeck", "get", "bbt", self.beiboot_name])
        except Exception:
            raise RuntimeError(
                f"Beiboot object '{self.beiboot_name}' does not exist or is not readable"
            )
        return output

    def _get_shelf_data(self, kubectl: Callable, shelf_name: str) -> dict:
        try:
            output = kubectl(["-n", "getdeck", "get", "shelf", shelf_name])
        except Exception:
            raise RuntimeError(
                f"Shelf object '{shelf_name}' does not exist or is not readable"
            )
        return output
