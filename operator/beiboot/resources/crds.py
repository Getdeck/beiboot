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
            "providerConfig": k8s.client.V1JSONSchemaProps(
                type="object", x_kubernetes_preserve_unknown_fields=True
            ),
            "ports": k8s.client.V1JSONSchemaProps(
                type="array",
                default=[],
                items=k8s.client.V1JSONSchemaProps(type="string"),
            ),
            "kubeconfig": k8s.client.V1JSONSchemaProps(
                type="object", x_kubernetes_preserve_unknown_fields=True
            ),
            "gefyra": k8s.client.V1JSONSchemaProps(
                type="object", x_kubernetes_preserve_unknown_fields=True
            ),
            "state": k8s.client.V1JSONSchemaProps(type="string", default="REQUESTED"),
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
