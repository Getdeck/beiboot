import base64


def compose_kubeconfig_for_serviceaccount(
    server: str, ca: str, namespace: str, token: str
):
    return f"""apiVersion: v1
kind: Config
clusters:
  - name: default-cluster
    cluster:
      certificate-authority-data: {base64.b64encode(ca.encode("utf-8")).decode("utf-8")}
      server: {server}
contexts:
  - name: default-context
    context:
      cluster: default-cluster
      namespace: {namespace}
      user: default-user
current-context: default-context
users:
  - name: default-user
    user:
      token: {token}
    """
