"""Tests for clashctl.proxy — config generation and node extraction."""

import os
from unittest.mock import patch

import pytest

from clashctl.proxy import (
    _get_proxies_list,
    _make_auto_group,
    _make_select_group,
    _build_base_config,
    generate_full_config,
)


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def multi_proxy_config():
    """A config dict with multiple proxy nodes."""
    return {
        "proxies": [
            {"name": "node-1", "type": "ss", "server": "s1.example.com", "port": 443},
            {"name": "node-2", "type": "vmess", "server": "s2.example.com", "port": 443},
            {"name": "node-3", "type": "trojan", "server": "s3.example.com", "port": 443},
        ],
        "proxy-groups": [
            {"name": "auto", "type": "url-test", "proxies": ["node-1", "node-2", "node-3"]},
        ],
        "rules": ["MATCH,auto"],
    }


@pytest.fixture
def empty_config():
    """A config with no proxies."""
    return {
        "proxies": [],
        "proxy-groups": [],
        "rules": ["MATCH,DIRECT"],
    }


# ── _get_proxies_list ────────────────────────────────────────────────────


class TestGetProxiesList:
    """Test get_node_names / _get_proxies_list."""

    def test_extracts_names_from_config(self, multi_proxy_config):
        names = _get_proxies_list(multi_proxy_config)
        assert names == ["node-1", "node-2", "node-3"]

    def test_empty_proxies(self, empty_config):
        names = _get_proxies_list(empty_config)
        assert names == []

    def test_no_proxies_key(self):
        names = _get_proxies_list({"mode": "rule"})
        assert names == []

    def test_skips_entries_without_name(self):
        cfg = {
            "proxies": [
                {"name": "valid", "type": "ss"},
                {"type": "ss", "server": "anon.example.com"},  # no name
                {"name": "", "type": "ss"},  # empty name
            ]
        }
        names = _get_proxies_list(cfg)
        assert names == ["valid"]

    def test_with_sample_config(self, sample_config):
        names = _get_proxies_list(sample_config)
        assert "test-node" in names


# ── _make_auto_group / _make_select_group ────────────────────────────────


class TestProxyGroups:
    def test_auto_group_structure(self):
        group = _make_auto_group(["a", "b", "c"])
        assert group["name"] == "auto"
        assert group["type"] == "url-test"
        assert group["proxies"] == ["a", "b", "c"]
        assert "url" in group
        assert "interval" in group

    def test_select_group_structure(self):
        group = _make_select_group(["x", "y"])
        assert group["name"] == "GLOBAL"
        assert group["type"] == "select"
        # auto should be first
        assert group["proxies"][0] == "auto"
        assert "x" in group["proxies"]
        assert "y" in group["proxies"]

    def test_select_group_with_no_nodes(self):
        group = _make_select_group([])
        assert group["proxies"] == ["auto"]

    def test_auto_group_with_single_node(self):
        group = _make_auto_group(["solo"])
        assert group["proxies"] == ["solo"]


# ── _build_base_config ──────────────────────────────────────────────────


class TestBuildBaseConfig:
    def test_has_required_keys(self):
        cfg = _build_base_config()
        required = [
            "mixed-port", "allow-lan", "bind-address", "mode",
            "log-level", "tun", "dns", "proxies", "proxy-groups",
            "rules", "rule-providers",
        ]
        for key in required:
            assert key in cfg, f"Missing key: {key}"

    def test_default_mode_is_rule(self):
        cfg = _build_base_config()
        assert cfg["mode"] == "rule"

    def test_empty_lists(self):
        cfg = _build_base_config()
        assert cfg["proxies"] == []
        assert cfg["proxy-groups"] == []
        assert cfg["rules"] == []

    def test_tun_config(self):
        cfg = _build_base_config()
        assert cfg["tun"]["enable"] is True
        assert cfg["tun"]["stack"] == "system"


# ── generate_full_config ────────────────────────────────────────────────


class TestGenerateFullConfig:
    """Test build_config / generate_full_config for all modes."""

    @pytest.fixture(autouse=True)
    def _patch_config_paths(self, tmp_path, monkeypatch):
        """Redirect file I/O for proxy module."""
        monkeypatch.setattr("clashctl.proxy.CONFIG_YAML", str(tmp_path / "config.yaml"))
        monkeypatch.setattr("clashctl.proxy.CUSTOM_RULES_YAML", str(tmp_path / "custom.yaml"))

    def _sample_proxies(self):
        return [
            {"name": "node-1", "type": "ss", "server": "1.2.3.4", "port": 443, "cipher": "aes-256-gcm", "password": "p"},
            {"name": "node-2", "type": "ss", "server": "5.6.7.8", "port": 443, "cipher": "aes-256-gcm", "password": "q"},
        ]

    def test_rule_mode(self):
        cfg = generate_full_config(proxies=self._sample_proxies(), mode="rule")
        assert isinstance(cfg, dict)
        assert cfg["mode"] == "rule"
        assert len(cfg["proxies"]) == 2
        # Should have proxy-groups (auto group)
        assert len(cfg["proxy-groups"]) >= 1
        auto_names = [g["name"] for g in cfg["proxy-groups"]]
        assert "auto" in auto_names
        # Rules should be from preset
        assert len(cfg["rules"]) > 0
        assert any("MATCH" in r for r in cfg["rules"])

    def test_global_mode(self):
        cfg = generate_full_config(proxies=self._sample_proxies(), mode="global")
        assert cfg["mode"] == "global"
        # Should have auto + GLOBAL groups
        group_names = [g["name"] for g in cfg["proxy-groups"]]
        assert "auto" in group_names
        assert "GLOBAL" in group_names
        # Rules should route to GLOBAL
        assert any("MATCH,GLOBAL" in r for r in cfg["rules"])

    def test_direct_mode(self):
        cfg = generate_full_config(proxies=self._sample_proxies(), mode="direct")
        assert cfg["mode"] == "direct"
        # No proxy groups in direct mode
        assert cfg["proxy-groups"] == []
        # Should route to DIRECT
        assert any("MATCH,DIRECT" in r for r in cfg["rules"])

    def test_empty_proxies(self):
        cfg = generate_full_config(proxies=[], mode="rule")
        assert cfg["proxies"] == []
        assert cfg["mode"] == "rule"

    def test_no_proxies_arg_defaults_to_empty(self):
        cfg = generate_full_config(mode="rule")
        assert cfg["proxies"] == []

    def test_contains_dns_config(self):
        cfg = generate_full_config(mode="rule")
        assert "dns" in cfg
        assert cfg["dns"]["enable"] is True
        assert "enhanced-mode" in cfg["dns"]
        assert "nameserver" in cfg["dns"]

    def test_contains_tun_config(self):
        cfg = generate_full_config(mode="rule")
        assert "tun" in cfg
        assert cfg["tun"]["enable"] is True

    def test_contains_rule_providers(self):
        cfg = generate_full_config(mode="rule")
        assert "rule-providers" in cfg
        assert isinstance(cfg["rule-providers"], dict)
        assert len(cfg["rule-providers"]) > 0

    def test_dns_preset_fake_ip(self):
        cfg = generate_full_config(mode="rule", dns_preset="fake-ip")
        assert cfg["dns"]["enhanced-mode"] == "fake-ip"
        assert "fake-ip-range" in cfg["dns"]
        assert "fake-ip-filter" in cfg["dns"]

    def test_dns_preset_redir_host(self):
        cfg = generate_full_config(mode="rule", dns_preset="redir-host")
        assert cfg["dns"]["enhanced-mode"] == "redir-host"

    def test_rule_preset_smart_split(self):
        cfg = generate_full_config(mode="rule", rule_preset="smart-split")
        assert any("geosite-cn" in r for r in cfg["rules"])
        assert any("geoip-cn" in r for r in cfg["rules"])

    def test_rule_preset_all_proxy(self):
        cfg = generate_full_config(mode="rule", rule_preset="all-proxy")
        assert any("MATCH,auto" in r for r in cfg["rules"])

    def test_proxies_preserved_in_output(self):
        proxies = self._sample_proxies()
        cfg = generate_full_config(proxies=proxies, mode="rule")
        assert cfg["proxies"] is proxies  # same list object

    def test_invalid_preset_falls_back(self):
        cfg = generate_full_config(mode="rule", rule_preset="nonexistent-preset")
        # Should fall back to smart-split
        assert len(cfg["rules"]) > 0

    def test_config_is_valid_dict(self):
        """Full config should be a dict that could be serialized to YAML."""
        import json
        cfg = generate_full_config(proxies=self._sample_proxies(), mode="rule")
        # Should be JSON-serializable (YAML is a superset)
        serialized = json.dumps(cfg)
        assert len(serialized) > 0
        deserialized = json.loads(serialized)
        assert deserialized == cfg
