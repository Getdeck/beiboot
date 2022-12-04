import logging

import kopf
import pytest


def test_k3s_image_tag():
    from beiboot.configuration import ClusterConfiguration, BeibootConfiguration
    from beiboot.provider.k3s import K3s

    parameters = ClusterConfiguration()

    for v in ["v1.24.8", "v1.25.4", "V1.23.13", "1.24.6"]:
        parameters.k8sVersion = v
        provider = K3s(
            BeibootConfiguration(),
            parameters,
            "test",
            "test_ns",
            ["8080:80"],
            logging.getLogger(),
        )
        assert provider.k3s_image_tag == f"v{v.strip('v').strip('V')}-k3s1"

    for v in ["k1.24.8", "2.25.4", "v1.a.13"]:
        parameters.k8sVersion = v
        provider = K3s(
            BeibootConfiguration(),
            parameters,
            "test",
            "test_ns",
            ["8080:80"],
            logging.getLogger(),
        )
        with pytest.raises(kopf.PermanentError):
            provider.k3s_image_tag
