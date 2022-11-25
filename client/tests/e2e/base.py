import json
import logging
from time import sleep
from typing import Callable

import pytest


class TestClientBase:

    beiboot_name = ""

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
                        f"State is: {str(data.get('state'))} | waiting for {state} | time: {str(_i)}"
                    )
                _i = _i + 1
                sleep(1)
        else:
            raise pytest.fail(
                f"The Beiboot never entered {state} state (timeout: {timeout})"
            )
