import kubernetes

from beiboot.configuration import ClusterConfiguration
from unittest import TestCase


def test_initial_configuration():
    initial_config = ClusterConfiguration()
    # test the current default configuration for Beiboot clusters
    assert initial_config.gefyra.get("enabled") is True
    assert initial_config.gefyra.get("endpoint") is None
    assert initial_config.nodes == 2


def test_merged_configuration():
    config = ClusterConfiguration()
    config.update({"nodes": 1})
    assert type(config.nodes) == int
    assert config.nodes == 1
    config.update({"nodes": 3})
    assert config.nodes == 3
    config.update({"nodes": "4"})
    assert config.nodes == 4

    config.update({"gefyra": {"enabled": False}})
    assert config.gefyra.get("enabled") is False
    config.update({"gefyra": {"enabled": True}})
    assert config.gefyra.get("enabled") is True
    config.update({"gefyra": {"enabled": "true"}})
    assert config.gefyra.get("enabled") is True
    config.update({"tunnel": {"enabled": False}})
    assert config.gefyra.get("enabled") is True
    assert config.tunnel.get("enabled") is False

    assert config.nodeStorageRequests == "10Gi"
    config.update({"nodeStorageRequests": "15Gi"})
    assert config.nodeStorageRequests == "15Gi"

    tc = TestCase()
    tc.assertDictEqual(
        {
            "requests": {"cpu": "1", "memory": "1Gi"},
            "limits": {},
        },
        config.nodeResources,
    )
    config.update({"nodeResources": {"requests": {"cpu": "2"}}})
    tc.assertDictEqual(
        {
            "requests": {"cpu": "2", "memory": "1Gi"},
            "limits": {},
        },
        config.nodeResources,
    )
    config.update({"nodeResources": {"requests": {"memory": "5Gi"}}})
    tc.assertDictEqual(
        {
            "requests": {"cpu": "2", "memory": "5Gi"},
            "limits": {},
        },
        config.nodeResources,
    )

    config.update(
        {
            "nodeResources": {
                "requests": {"cpu": "3", "memory": "4Gi"},
                "limits": {"memory": "8Gi"},
            }
        }
    )
    tc.assertDictEqual(
        {
            "requests": {"cpu": "3", "memory": "4Gi"},
            "limits": {"memory": "8Gi"},
        },
        config.nodeResources,
    )

    assert config.maxLifetime is None
    assert config.clusterReadyTimeout == 180
    assert config.ports is None
    config.update(
        {
            "nodes": "3",
            "nodeResources": {
                "requests": {"cpu": "2", "memory": "2Gi"},
                "limits": {"memory": "42Gi"},
            },
            "maxLifetime": "2h",
            "clusterReadyTimeout": 80,
            "ports": ["8080:80", "8443:443"],
        }
    )
    assert config.maxLifetime == "2h"
    assert config.clusterReadyTimeout == 80
    assert config.ports == ["8080:80", "8443:443"]
    assert config.nodes == 3
    tc.assertDictEqual(
        {"requests": {"cpu": "2", "memory": "2Gi"}, "limits": {"memory": "42Gi"}},
        config.nodeResources,
    )


def test_encode_configuration():
    config = ClusterConfiguration()
    data = config.encode_cluster_configuration()
    tc = TestCase()
    tc.assertDictEqual(
        {
            "k8sVersion": "null",
            "nodes": "2",
            "nodeLabels": '{"app": "beiboot", "beiboot.dev/is-node": "true"}',
            "serverLabels": '{"app": "beiboot", "beiboot.dev/is-node": "true", "beiboot.dev/is-server": "true"}',
            "serverResources": '{"requests": {"cpu": "1", "memory": "1Gi"}, "limits": {}}',
            "serverStorageRequests": "10Gi",
            "nodeResources": '{"requests": {"cpu": "1", "memory": "1Gi"}, "limits": {}}',
            "nodeStorageRequests": "10Gi",
            "namespacePrefix": "getdeck-bbt",
            "serverStartupTimeout": "60",
            "apiServerContainerName": "apiserver",
            "kubeconfigFromLocation": "/getdeck/kube-config.yaml",
            "clusterReadyTimeout": "180",
            "gefyra": '{"enabled": true, "endpoint": null}',
            "tunnel": '{"enabled": true, "endpoint": null}',
            "ports": "null",
            "maxLifetime": "null",
            "maxSessionTimeout": "null",
            "k3sImage": "rancher/k3s",
            "k3sImageTag": "v1.24.3-k3s1",
            "k3sImagePullPolicy": "IfNotPresent",
        },
        data,
    )


def test_decode_configuration():
    serialized = {
        "k8sVersion": "null",
        "nodes": "3",
        "nodeLabels": '{"app": "beiboot", "beiboot.dev/is-node": "true"}',
        "serverLabels": '{"app": "beiboot", "beiboot.dev/is-node": "true", "beiboot.dev/is-server": "true"}',
        "serverResources": '{"requests": {"cpu": "1", "memory": "1Gi"}, "limits": {}}',
        "serverStorageRequests": "10Gi",
        "nodeResources": '{"requests": {"cpu": "1", "memory": "1Gi"}, "limits": {}}',
        "nodeStorageRequests": "10Gi",
        "namespacePrefix": "getdeck-bbt",
        "serverStartupTimeout": "60",
        "apiServerContainerName": "apiserver",
        "kubeconfigFromLocation": "/getdeck/kube-config.yaml",
        "clusterReadyTimeout": "80",
        "gefyra": '{"enabled": false, "endpoint": null}',
        "ports": '["8080:80", "8443:443"]',
        "maxLifetime": "2h",
        "maxSessionTimeout": "null",
        "k3sImage": "rancher/k3s",
        "k3sImageTag": "v1.24.3-k3s1",
        "k3sImagePullPolicy": "IfNotPresent",
    }
    configmap = kubernetes.client.V1ConfigMap(data=serialized)
    config = ClusterConfiguration().decode_cluster_configuration(configmap)
    assert config.maxLifetime == "2h"
    assert config.clusterReadyTimeout == 80
    assert config.ports == ["8080:80", "8443:443"]
    assert config.nodes == 3
    assert config.gefyra.get("enabled") is False
    assert config.tunnel.get("enabled") is True
