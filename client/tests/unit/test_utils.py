from beiboot.types import BeibootParameters, BeibootRequest


def test_beiboot_params():
    data = BeibootParameters.from_raw({"nodes": 3, "maxLifetime": "2h"})
    assert data.nodes == 3
    assert data.lifetime == "2h"
    assert data.ports is None

    _dict = data.as_dict()
    assert _dict["nodes"] == 3
    assert _dict["lifetime"] == "2h"
    assert "ports" not in _dict
    assert type(_dict["gefyra"]) == dict


def test_beiboot_request():
    req = BeibootRequest(name="mycluster")
    assert req.name == "mycluster"
    assert req.parameters.nodes is None
    assert req.parameters == BeibootParameters()
