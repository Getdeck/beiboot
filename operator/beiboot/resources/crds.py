import kubernetes as k8s


BEIBOOT_PARAMETERS = k8s.client.V1JSONSchemaProps(
    type="object",
    properties={
        "k8sVersion": k8s.client.V1JSONSchemaProps(type="string"),
        # the forwarding for cluster ports in the form ['8080:80, '8443: 443']
        "ports": k8s.client.V1JSONSchemaProps(
            type="array",
            default=[],
            items=k8s.client.V1JSONSchemaProps(type="string"),
        ),
        # the amount of nodes for this cluster
        "nodes": k8s.client.V1JSONSchemaProps(type="integer"),
        # total time a cluster can exist, starts counting when cluster is ready
        "maxLifetime": k8s.client.V1JSONSchemaProps(type="string"),
        # max time with no client heartbeat before the cluster extincts
        "maxSessionTimeout": k8s.client.V1JSONSchemaProps(type="string"),
        # timeout for this cluster to become ready
        "clusterReadyTimeout": k8s.client.V1JSONSchemaProps(type="integer"),
        # server resources
        "serverResources": k8s.client.V1JSONSchemaProps(
            type="object",
            properties={
                "requests": k8s.client.V1JSONSchemaProps(
                    type="object",
                    properties={
                        "cpu": k8s.client.V1JSONSchemaProps(type="string"),
                        "memory": k8s.client.V1JSONSchemaProps(type="string"),
                    },
                ),
                "limits": k8s.client.V1JSONSchemaProps(
                    type="object",
                    properties={
                        "cpu": k8s.client.V1JSONSchemaProps(type="string"),
                        "memory": k8s.client.V1JSONSchemaProps(type="string"),
                    },
                ),
            },
        ),
        # node resources
        "nodeResources": k8s.client.V1JSONSchemaProps(
            type="object",
            properties={
                "requests": k8s.client.V1JSONSchemaProps(
                    type="object",
                    properties={
                        "cpu": k8s.client.V1JSONSchemaProps(type="string"),
                        "memory": k8s.client.V1JSONSchemaProps(type="string"),
                    },
                ),
                "limits": k8s.client.V1JSONSchemaProps(
                    type="object",
                    properties={
                        "cpu": k8s.client.V1JSONSchemaProps(type="string"),
                        "memory": k8s.client.V1JSONSchemaProps(type="string"),
                    },
                ),
            },
        ),
        "serverStorageRequests": k8s.client.V1JSONSchemaProps(type="string"),
        "nodeStorageRequests": k8s.client.V1JSONSchemaProps(type="string"),
        "gefyra": k8s.client.V1JSONSchemaProps(
            type="object",
            properties={
                "enabled": k8s.client.V1JSONSchemaProps(type="boolean"),
                "endpoint": k8s.client.V1JSONSchemaProps(type="string"),
            },
        ),
        "tunnel": k8s.client.V1JSONSchemaProps(
            type="object",
            properties={
                "enabled": k8s.client.V1JSONSchemaProps(type="boolean"),
                "endpoint": k8s.client.V1JSONSchemaProps(type="string"),
            },
        ),
    },
)


def create_beiboot_definition(namespace: str) -> k8s.client.V1CustomResourceDefinition:
    schema_props = k8s.client.V1JSONSchemaProps(
        type="object",
        required=["provider"],
        properties={
            "provider": k8s.client.V1JSONSchemaProps(type="string", enum=["k3s"]),
            "beibootNamespace": k8s.client.V1JSONSchemaProps(type="string"),
            "nodeToken": k8s.client.V1JSONSchemaProps(type="string"),
            "fromShelf": k8s.client.V1JSONSchemaProps(type="string"),
            "parameters": BEIBOOT_PARAMETERS,
            "kubeconfig": k8s.client.V1JSONSchemaProps(
                type="object", x_kubernetes_preserve_unknown_fields=True
            ),
            "gefyra": k8s.client.V1JSONSchemaProps(
                type="object",
                default={},
                properties={
                    "endpoint": k8s.client.V1JSONSchemaProps(type="string"),
                    "port": k8s.client.V1JSONSchemaProps(type="string"),
                },
            ),
            "sunset": k8s.client.V1JSONSchemaProps(type="string"),
            "lastClientContact": k8s.client.V1JSONSchemaProps(type="string"),
            "tunnel": k8s.client.V1JSONSchemaProps(
                type="object", x_kubernetes_preserve_unknown_fields=True
            ),
            "state": k8s.client.V1JSONSchemaProps(type="string", default="REQUESTED"),
            "stateTransitions": k8s.client.V1JSONSchemaProps(
                type="object", x_kubernetes_preserve_unknown_fields=True
            ),
            "status": k8s.client.V1JSONSchemaProps(
                type="object", x_kubernetes_preserve_unknown_fields=True
            ),
        },
    )

    def_spec = k8s.client.V1CustomResourceDefinitionSpec(
        group="getdeck.dev",
        names=k8s.client.V1CustomResourceDefinitionNames(
            kind="beiboot",
            plural="beiboots",
            short_names=["bbt"],
        ),
        scope="Namespaced",
        versions=[
            k8s.client.V1CustomResourceDefinitionVersion(
                name="v1",
                served=True,
                storage=True,
                schema=k8s.client.V1CustomResourceValidation(
                    open_apiv3_schema=schema_props
                ),
            )
        ],
    )

    crd = k8s.client.V1CustomResourceDefinition(
        api_version="apiextensions.k8s.io/v1",
        kind="CustomResourceDefinition",
        spec=def_spec,
        metadata=k8s.client.V1ObjectMeta(
            name="beiboots.getdeck.dev",
            namespace=namespace,
            finalizers=[],
        ),
    )
    return crd


def create_shelf_definition(namespace: str) -> k8s.client.V1CustomResourceDefinition:
    schema_props = k8s.client.V1JSONSchemaProps(
        type="object",
        properties={
            # example of a volumeSnapshotContent:
            #   name: snapcontent-155f3d59-d89f-41de-9135-31eba2d2c3ef
            #   snapshotHandle: provider/specific/path/to/handle/155f3d59-d89f-41de-9135-31eba2d2c3ef
            #   node: server
            #   pvc: k8s-server-data-server-0
            #   volumeSnapshotName: example-server
            "volumeSnapshotContents": k8s.client.V1JSONSchemaProps(
                type="array",
                default=[],
                items=k8s.client.V1JSONSchemaProps(
                    type="object",
                    properties={
                        "name": k8s.client.V1JSONSchemaProps(type="string", default=""),
                        "node": k8s.client.V1JSONSchemaProps(type="string", default=""),
                        "pvc": k8s.client.V1JSONSchemaProps(type="string", default=""),
                        "snapshotHandle": k8s.client.V1JSONSchemaProps(
                            type="string", default=""
                        ),
                        "volumeSnapshotName": k8s.client.V1JSONSchemaProps(
                            type="string", default=""
                        ),
                    },
                ),
            ),
            "volumeSnapshotClass": k8s.client.V1JSONSchemaProps(
                type="string", default=""
            ),
            "clusterName": k8s.client.V1JSONSchemaProps(type="string", default=""),
            "clusterNamespace": k8s.client.V1JSONSchemaProps(type="string", default=""),
            # copy of the parameters with which the beiboot cluster originally was provisioned
            "clusterParameters": BEIBOOT_PARAMETERS,
            # free data that the cluster provider might use
            "providerData": k8s.client.V1JSONSchemaProps(
                type="object", x_kubernetes_preserve_unknown_fields=True
            ),
            "state": k8s.client.V1JSONSchemaProps(type="string", default="REQUESTED"),
            "stateTransitions": k8s.client.V1JSONSchemaProps(
                type="object", x_kubernetes_preserve_unknown_fields=True
            ),
            "status": k8s.client.V1JSONSchemaProps(
                type="object", x_kubernetes_preserve_unknown_fields=True
            ),
            "created": k8s.client.V1JSONSchemaProps(type="string"),
        },
    )

    def_spec = k8s.client.V1CustomResourceDefinitionSpec(
        group="beiboots.getdeck.dev",
        names=k8s.client.V1CustomResourceDefinitionNames(
            kind="shelf",
            plural="shelves",
        ),
        scope="Namespaced",
        versions=[
            k8s.client.V1CustomResourceDefinitionVersion(
                name="v1",
                served=True,
                storage=True,
                schema=k8s.client.V1CustomResourceValidation(
                    open_apiv3_schema=schema_props
                ),
            )
        ],
    )

    crd = k8s.client.V1CustomResourceDefinition(
        api_version="apiextensions.k8s.io/v1",
        kind="CustomResourceDefinition",
        spec=def_spec,
        metadata=k8s.client.V1ObjectMeta(
            name="shelves.beiboots.getdeck.dev",
            namespace=namespace,
            finalizers=[],
        ),
    )
    return crd
