import json
import yaml
import pytest

from beiboot.misc.install import (
    synthesize_config_as_dict,
    synthesize_config_as_json,
    synthesize_config_as_yaml,
)
from beiboot.types import InstallOptions

options = InstallOptions(namespace="getdeck")


def test_get_all_raw_configs():

    d = synthesize_config_as_dict(options)
    assert len(d) == 9


def test_get_custom_version_configs():
    coptions = InstallOptions(namespace="getdeck", version="1.0.0")
    d = synthesize_config_as_dict(coptions)
    for el in d:
        if el.get("kind") == "Deployment" and el.get("metadata", {}).get("name") == "beiboot-operator":
            assert (
                el["spec"]["template"]["spec"]["containers"][0]["image"]
                == "quay.io/getdeck/beiboot:1.0.0"
            )


def test_get_comp1_raw_configs():

    d = synthesize_config_as_dict(options, components=["deployment"])
    assert len(d) == 1


def test_get_missing_comp_raw_configs():

    with pytest.raises(RuntimeError):
        synthesize_config_as_dict(options, components=["deploymen", "webhook"])


def test_get_all_configs_json():
    j = synthesize_config_as_json(options)
    json.loads(j)


def test_get_all_configs_yaml():
    y = synthesize_config_as_yaml(options)
    docs = list(yaml.load_all(y, Loader=yaml.FullLoader))
    assert len(docs) == 9
