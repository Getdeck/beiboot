# flake8: noqa
from beiboot.types import InstallOptions


def data(params: InstallOptions) -> list[dict]:
    return [
        {
            "apiVersion": "v1",
            "kind": "ServiceAccount",
            "metadata": {"namespace": params.namespace, "name": "beiboot-operator"},
        },
        {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "ClusterRole",
            "metadata": {"name": "getdeck:beiboot:operator"},
            "rules": [
                {
                    "apiGroups": ["kopf.dev"],
                    "resources": ["clusterkopfpeerings"],
                    "verbs": ["list", "watch", "patch", "get"],
                },
                {
                    "apiGroups": ["apiextensions.k8s.io"],
                    "resources": ["customresourcedefinitions"],
                    "verbs": ["create", "patch", "delete", "list", "watch"],
                },
                {
                    "apiGroups": ["admissionregistration.k8s.io"],
                    "resources": [
                        "validatingwebhookconfigurations",
                        "mutatingwebhookconfigurations",
                    ],
                    "verbs": ["create", "patch"],
                },
                {
                    "apiGroups": [
                        "",
                        "apps",
                        "batch",
                        "extensions",
                        "events.k8s.io",
                        "rbac.authorization.k8s.io",
                    ],
                    "resources": [
                        "namespaces",
                        "roles",
                        "serviceaccounts",
                        "rolebindings",
                        "nodes",
                        "configmaps",
                        "secrets",
                        "deployments",
                        "statefulsets",
                        "persistentvolumeclaims",
                        "services",
                        "pods",
                        "pods/exec",
                        "events",
                    ],
                    "verbs": ["*"],
                },
                {
                    "apiGroups": ["getdeck.dev"],
                    "resources": ["beiboots"],
                    "verbs": ["*"],
                },
                {
                    "apiGroups": ["beiboots.getdeck.dev"],
                    "resources": ["shelves"],
                    "verbs": ["*"],
                },
                {
                    "apiGroups": ["snapshot.storage.k8s.io"],
                    "resources": [
                        "volumesnapshots",
                        "volumesnapshotcontents",
                        "volumesnapshotclasses",
                    ],
                    "verbs": ["*"],
                },
            ],
        },
        {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "ClusterRoleBinding",
            "metadata": {
                "name": "getdeck-beiboot-operator",
                "namespace": params.namespace,
            },
            "roleRef": {
                "apiGroup": "rbac.authorization.k8s.io",
                "kind": "ClusterRole",
                "name": "getdeck:beiboot:operator",
            },
            "subjects": [
                {
                    "kind": "ServiceAccount",
                    "name": "beiboot-operator",
                    "namespace": params.namespace,
                }
            ],
        },
    ]
