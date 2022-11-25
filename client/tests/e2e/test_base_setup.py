import logging
from time import sleep


class TestBaseSetup:
    def test_sane_operator(self, operator, kubectl):
        output = kubectl(
            ["-n", "getdeck", "apply", "-f", "tests/fixtures/simple-beiboot.yaml"]
        )
        _i = 0
        while _i < 60:
            output = kubectl(
                [
                    "-n",
                    "getdeck",
                    "get",
                    "bbt",
                    "test-beiboot",
                    "-o",
                    "jsonpath={.state}",
                ]
            )
            if output == "READY":
                break
            logging.getLogger().info(output)
            sleep(1)
