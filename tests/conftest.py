"""Shared test fixtures for qubes-clash-gateway."""

import json
import os
import shutil
import tempfile

import pytest


@pytest.fixture
def tmp_clash_dir(tmp_path):
    """Create a temporary clash config directory structure."""
    clash_dir = tmp_path / "clash"
    clash_dir.mkdir()
    (clash_dir / "rule-providers").mkdir()
    return clash_dir


@pytest.fixture
def sample_config():
    """A minimal valid mihomo config dict."""
    return {
        "mixed-port": 7890,
        "allow-lan": True,
        "bind-address": "*",
        "mode": "rule",
        "log-level": "info",
        "external-controller": "127.0.0.1:9090",
        "dns": {
            "enable": True,
            "listen": "0.0.0.0:1053",
            "enhanced-mode": "fake-ip",
            "fake-ip-range": "198.18.0.1/16",
            "nameserver": ["8.8.8.8"],
        },
        "proxies": [
            {
                "name": "test-node",
                "type": "ss",
                "server": "example.com",
                "port": 443,
                "cipher": "aes-256-gcm",
                "password": "test-password",
            }
        ],
        "proxy-groups": [
            {
                "name": "auto",
                "type": "url-test",
                "proxies": ["test-node"],
                "url": "http://www.gstatic.com/generate_204",
                "interval": 300,
            }
        ],
        "rules": [
            "GEOSITE,cn,DIRECT",
            "GEOIP,CN,DIRECT",
            "MATCH,auto",
        ],
    }


@pytest.fixture
def sample_config_yaml(sample_config):
    """Sample config as YAML string."""
    try:
        import yaml
        return yaml.dump(sample_config, allow_unicode=True)
    except ImportError:
        # Fallback: minimal YAML representation
        return (
            "mixed-port: 7890\n"
            "allow-lan: true\n"
            "mode: rule\n"
            "external-controller: 127.0.0.1:9090\n"
        )


@pytest.fixture
def sample_subscriptions():
    """Parsed subscription data."""
    return {
        "url": "https://example.com/sub",
        "name": "test-sub",
        "updated_at": "2026-06-02T12:00:00",
        "nodes": [
            {
                "name": "node-1",
                "type": "ss",
                "server": "s1.example.com",
                "port": 443,
                "cipher": "aes-256-gcm",
                "password": "pass1",
            },
            {
                "name": "node-2",
                "type": "vmess",
                "server": "s2.example.com",
                "port": 443,
                "uuid": "test-uuid",
                "alterId": 0,
                "cipher": "auto",
            },
        ],
    }


@pytest.fixture
def sample_ss_uri():
    """Sample Shadowsocks subscription URI (base64-encoded)."""
    import base64

    nodes = [
        "- name: node-1\n  type: ss\n  server: s1.example.com\n  port: 443\n  cipher: aes-256-gcm\n  password: pass1",
        "- name: node-2\n  type: ss\n  server: s2.example.com\n  port: 8443\n  cipher: chacha20-ietf-poly1305\n  password: pass2",
    ]
    yaml_content = "proxies:\n" + "\n".join(nodes)
    return base64.b64encode(yaml_content.encode()).decode()


@pytest.fixture
def mock_preferences():
    """Sample preferences dict."""
    return {
        "mode": "rule",
        "selected_node": "test-node",
        "dns_mode": "fake-ip",
        "language": "zh",
    }
