# flake8: noqa
from beiboot.types import InstallOptions


def data(params: InstallOptions) -> list[dict]:
    return [
        {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {"name": params.namespace},
        }
    ]
