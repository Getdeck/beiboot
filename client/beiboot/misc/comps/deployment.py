# flake8: noqa
from beiboot.types import InstallOptions


def data(params: InstallOptions) -> list[dict]:
    return [
        {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": "beiboot-operator",
                "namespace": params.namespace,
                "labels": {"app": "beiboot-operator"},
            },
            "spec": {
                "replicas": 1,
                "selector": {"matchLabels": {"app": "beiboot-operator"}},
                "template": {
                    "metadata": {"labels": {"app": "beiboot-operator"}},
                    "spec": {
                        "serviceAccountName": "beiboot-operator",
                        "containers": [
                            {
                                "name": "beiboot",
                                "image": f"quay.io/getdeck/beiboot:{params.version}",
                                "imagePullPolicy": "Always",
                                "ports": [{"containerPort": 9443}],
                            }
                        ],
                    },
                },
            },
        }
    ]
