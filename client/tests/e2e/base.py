import json
import logging
from time import sleep
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
                    serverResources={
                        "requests": {"cpu": "0.25", "memory": "0.25Gi"}
                    },
                    nodeResources={"requests": {"cpu": "0.25", "memory": "0.25Gi"}},
                    tunnel=TunnelParams(endpoint=minikube_ip),
                )
            else:
                params = BeibootParameters(
                    nodes=1,
                    serverStorageRequests="100Mi",
                    serverResources={
                        "requests": {"cpu": "0.25", "memory": "0.25Gi"}
                    },
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

    def _apply_fixture_file(self, path: str, kubectl: Callable, timeout: int):
        _i = 0
        while _i < timeout:
            output = kubectl(
                [
                    "-n",
                    "getdeck",
                    "apply",
                    "-f",
                    path,
                ]
            )
            if f"beiboot.getdeck.dev/{self.beiboot_name} created" in output:
                break
            else:
                _i = _i + 1
                sleep(1)
        else:
            logging.getLogger().warning(output)
            raise pytest.fail("The Beiboot object could not be created")

    def _get_beiboot_data(self, kubectl: Callable) -> dict:
        output = kubectl(
            ["-n", "getdeck", "get", "bbt", self.beiboot_name, "-o", "json"]
        )
        try:
            data = json.loads(output)
        except json.decoder.JSONDecodeError:
            raise RuntimeError("This Beiboot object does not exist or is not readable")
        return data

    def _get_shelf_data(self, kubectl: Callable, shelf_name: str) -> dict:
        output = kubectl(
            ["-n", "getdeck", "get", "shelf", shelf_name, "-o", "json"]
        )
        try:
            data = json.loads(output)
        except json.decoder.JSONDecodeError:
            raise RuntimeError("This Beiboot object does not exist or is not readable")
        return data

    def _wait_for_state(self, state: str, kubectl: Callable, timeout: int):
        logger = logging.getLogger()
        _i = 0
        while _i < timeout:
            data = self._get_beiboot_data(kubectl)
            if data.get("state") == state:
                break
            if data.get("state") == "ERROR" and state != "ERROR":
                raise pytest.fail(
                    f"The Beiboot entered ERROR state which was not expected (timeout: {timeout})"
                )
            else:
                if _i % 2:
                    logger.info(
                        f"Waiting for state {state} (is: {str(data.get('state'))}, {_i}s/{timeout}s)"
                    )
                _i = _i + 1
                sleep(1)
        else:
            raise pytest.fail(
                f"The Beiboot never entered {state} state (timeout: {timeout})"
            )
