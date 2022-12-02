from pathlib import Path

from beiboot.types import BeibootParameters, BeibootRequest
from beiboot.utils import (
    decode_b64_dict,
    get_beiboot_config_location,
    get_kubeconfig_location,
)


def test_beiboot_params():
    data = BeibootParameters.from_raw(
        {"nodes": 3, "maxLifetime": "2h", "gefyra": {"enabled": True}}
    )
    assert data.nodes == 3
    assert data.maxLifetime == "2h"
    assert data.ports is None

    _dict = data.as_dict()
    assert _dict["nodes"] == 3
    assert _dict["maxLifetime"] == "2h"
    assert "ports" not in _dict
    assert type(_dict["gefyra"]) == dict


def test_beiboot_request():
    req = BeibootRequest(name="mycluster")
    assert req.name == "mycluster"
    assert req.parameters.nodes is None
    assert req.parameters == BeibootParameters()


def test_encode_mtls_data():
    data = decode_b64_dict({"ca.crt": "aGVsbG8K", "client.crt": "Y2xpZW50Cg=="})
    assert data["ca.crt"] == "hello"
    assert data["client.crt"] == "client"


def test_config_paths():
    from beiboot.configuration import ClientConfiguration

    bbt_dir = get_beiboot_config_location(ClientConfiguration(), "mycluster")
    assert bbt_dir == str(Path.home().joinpath(".getdeck", "mycluster"))
    kubeconfig = get_kubeconfig_location(ClientConfiguration(), "mycluster")
    assert kubeconfig == str(
        Path.home().joinpath(".getdeck", "mycluster", "mycluster.yaml")
    )
