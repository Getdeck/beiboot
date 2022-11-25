import kubernetes as k8s

from beiboot.configuration import configuration


def create_beiboot_definition() -> k8s.client.V1CustomResourceDefinition:
    schema_props = k8s.client.V1JSONSchemaProps(
        type="object",
        required=["provider"],
        properties={
            "provider": k8s.client.V1JSONSchemaProps(type="string", enum=["k3s"]),
            "beibootNamespace": k8s.client.V1JSONSchemaProps(type="string"),
            "nodeToken": k8s.client.V1JSONSchemaProps(type="string"),
            "parameters": k8s.client.V1JSONSchemaProps(
                type="object",
                properties={
                    # the forwarding for cluster ports in the form ['8080:80, '8443: 443']
                    "ports": k8s.client.V1JSONSchemaProps(
                        type="array",
                        default=[],
                        items=k8s.client.V1JSONSchemaProps(type="string"),
                    ),
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
                                    "memory": k8s.client.V1JSONSchemaProps(
                                        type="string"
                                    ),
                                },
                            ),
                            "limits": k8s.client.V1JSONSchemaProps(
                                type="object",
                                properties={
                                    "cpu": k8s.client.V1JSONSchemaProps(type="string"),
                                    "memory": k8s.client.V1JSONSchemaProps(
                                        type="string"
                                    ),
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
                                    "memory": k8s.client.V1JSONSchemaProps(
                                        type="string"
                                    ),
                                },
                            ),
                            "limits": k8s.client.V1JSONSchemaProps(
                                type="object",
                                properties={
                                    "cpu": k8s.client.V1JSONSchemaProps(type="string"),
                                    "memory": k8s.client.V1JSONSchemaProps(
                                        type="string"
                                    ),
                                },
                            ),
                        },
                    ),
                    "serverStorageRequests": k8s.client.V1JSONSchemaProps(
                        type="string"
                    ),
                    "nodeStorageRequests": k8s.client.V1JSONSchemaProps(type="string"),
                    "gefyra": k8s.client.V1JSONSchemaProps(
                        type="object",
                        properties={
                            "enabled": k8s.client.V1JSONSchemaProps(
                                type="boolean"
                            ),
                            "endpoint": k8s.client.V1JSONSchemaProps(
                                type="string"
                            ),
                            "port": k8s.client.V1JSONSchemaProps(
                                type="string"
                            )
                        },
                    ),
                },
                x_kubernetes_preserve_unknown_fields=True,
            ),
            "kubeconfig": k8s.client.V1JSONSchemaProps(
                type="object", x_kubernetes_preserve_unknown_fields=True
            ),
            "sunset": k8s.client.V1JSONSchemaProps(type="string"),
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
            namespace=configuration.NAMESPACE,
            finalizers=[],
        ),
    )
    return crd
