import logging
from time import sleep

import kopf
import pytest

from beiboot.configuration import ClusterConfiguration


def test_parse_timedelta():
    from beiboot.utils import parse_timedelta
    from datetime import timedelta

    assert parse_timedelta("3d") == timedelta(days=3)
    assert parse_timedelta("2h30m") == timedelta(hours=2, minutes=30)
    assert parse_timedelta("30m") == timedelta(minutes=30)
    with pytest.raises(ValueError):
        assert parse_timedelta("-2h") == timedelta(hours=-3)
        assert parse_timedelta("-37D") == timedelta(days=-37)
    assert parse_timedelta("-30min", only_positve=False) == timedelta(minutes=-30)


def test_validator_ports():
    from beiboot.handler import validate_ports

    validate_ports("", {"ports": ["8080:9090"]}, None, logging.getLogger())
    validate_ports(
        "", {"ports": ["8080:9090", "9090:38948"]}, None, logging.getLogger()
    )
    with pytest.raises(kopf.AdmissionError):
        validate_ports("", {"ports": "blubb"}, None, logging.getLogger())
        validate_ports(
            "", {"ports": ["8080:9090", "6763:blubb"]}, None, logging.getLogger()
        )
        validate_ports(
            "", {"ports": ["8080:9090", "6763:blubb"]}, None, logging.getLogger()
        )
        validate_ports(
            "", {"ports": ["8080:9090", "6763blubb"]}, None, logging.getLogger()
        )
        validate_ports(
            "", {"ports": ["8080:9090", "9090:38948"]}, None, logging.getLogger()
        )
        validate_ports("", {"ports": ["-1:9090"]}, None, logging.getLogger())
        validate_ports("", {"ports": ["75000:9090"]}, None, logging.getLogger())


def test_validator_maxlifetime():
    from beiboot.handler import validate_maxlifetime

    validate_maxlifetime("", {"maxLifetime": "2d"}, None, logging.getLogger())
    validate_maxlifetime("", {"maxLifetime": "2h30m"}, None, logging.getLogger())
    validate_maxlifetime("", {"maxLifetime": "1h35m20s"}, None, logging.getLogger())
    validate_maxlifetime("", {"maxLifetime": "20s"}, None, logging.getLogger())
    with pytest.raises(kopf.AdmissionError):
        validate_maxlifetime("", {"maxLifetime": "1.5h"}, None, logging.getLogger())
        validate_maxlifetime(
            "", {"maxLifetime": "-1h35m20s"}, None, logging.getLogger()
        )


def test_validator_session_timeout():
    from beiboot.handler import validate_session_timeout

    validate_session_timeout("", {"maxSessionTimeout": "2d"}, None, logging.getLogger())
    validate_session_timeout(
        "", {"maxSessionTimeout": "2h30m"}, None, logging.getLogger()
    )
    validate_session_timeout(
        "", {"maxSessionTimeout": "1h35m20s"}, None, logging.getLogger()
    )
    validate_session_timeout(
        "", {"maxSessionTimeout": "1m"}, None, logging.getLogger()
    )
    with pytest.raises(kopf.AdmissionError):
        validate_session_timeout(
            "", {"maxSessionTimeout": "60s"}, None, logging.getLogger()
        )
        validate_session_timeout(
            "", {"maxSessionTimeout": "1.5h"}, None, logging.getLogger()
        )
        validate_session_timeout(
            "", {"maxSessionTimeout": "-1h35m20s"}, None, logging.getLogger()
        )


# def test_validator_namespace(kubeconfig, kubectl):
#     from beiboot.handler import validate_namespace
#
#     validate_namespace("valid-test", {}, ClusterConfiguration(), logging.getLogger())
#     kubectl(["create", "ns", "getdeck-bbt-valid-test"])
#     sleep(1)
#     with pytest.raises(kopf.AdmissionError):
#         validate_namespace(
#             "valid-test", {}, ClusterConfiguration(), logging.getLogger()
#         )
#
#
# def test_validation_webhook(kubeconfig, kubectl):
#     from beiboot.handler import check_validate_beiboot_request
#
#     check_validate_beiboot_request(
#         body={"metadata": {"name": "test"}, "parameters": {"maxLifetime": "20s"}},
#         logger=logging.getLogger(),
#         operation="CREATE",
#     )
#     check_validate_beiboot_request(
#         body={
#             "metadata": {"name": "test"},
#             "parameters": {"maxLifetime": "20s", "ports": ["8090:9090"]},
#         },
#         logger=logging.getLogger(),
#         operation="CREATE",
#     )
#     check_validate_beiboot_request(
#         body={"metadata": {"name": "test"}, "parameters": {"ports": ["8090:9090"]}},
#         logger=logging.getLogger(),
#         operation="CREATE",
#     )
#     with pytest.raises(kopf.AdmissionError):
#         check_validate_beiboot_request(
#             body={"metadata": {"name": "test"}, "parameters": {"ports": ["8090:ii"]}},
#             logger=logging.getLogger(),
#             operation="CREATE",
#         )
#         check_validate_beiboot_request(
#             body={"metadata": {"name": "test"}, "parameters": {"maxLifetime": "2k"}},
#             logger=logging.getLogger(),
#             operation="CREATE",
#         )
#         check_validate_beiboot_request(
#             body={
#                 "metadata": {"name": "test"},
#                 "parameters": {"ports": ["blubb"], "maxLifetime": "2k"},
#             },
#             logger=logging.getLogger(),
#             operation="CREATE",
#         )
#         check_validate_beiboot_request(
#             body={"metadata": {"name": "test"}, "parameters": {"ports": "blubb"}},
#             logger=logging.getLogger(),
#             operation="CREATE",
#         )
#         kubectl(["create", "ns", "getdeck-bbt-test"])
#         sleep(1)
#         check_validate_beiboot_request(
#             body={"metadata": {"name": "test"}, "parameters": {"ports": ["80:90"]}},
#             logger=logging.getLogger(),
#             operation="CREATE",
#         )
