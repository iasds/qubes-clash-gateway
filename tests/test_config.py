"""Tests for clashctl.config — constants, paths, and secret reading."""

import os
import pytest


class TestConstants:
    """Verify that expected module-level constants exist and have sane types/values."""

    def test_api_base_exists(self):
        from clashctl.config import API_BASE
        assert isinstance(API_BASE, str)
        assert API_BASE.startswith("http")

    def test_api_port_exists(self):
        from clashctl.config import API_PORT
        assert isinstance(API_PORT, int)
        assert 1 <= API_PORT <= 65535

    def test_speedtest_timeout_exists(self):
        from clashctl.config import SPEEDTEST_TIMEOUT
        assert isinstance(SPEEDTEST_TIMEOUT, (int, float))
        assert SPEEDTEST_TIMEOUT > 0

    def test_speedtest_workers_exists(self):
        from clashctl.config import SPEEDTEST_WORKERS
        assert isinstance(SPEEDTEST_WORKERS, int)
        assert SPEEDTEST_WORKERS > 0

    def test_color_codes(self):
        from clashctl.config import (
            C_RESET, C_BOLD, C_DIM,
            C_GREEN, C_YELLOW, C_RED,
            C_CYAN, C_GRAY, C_WHITE,
        )
        for code in (C_RESET, C_BOLD, C_DIM, C_GREEN, C_YELLOW,
                      C_RED, C_CYAN, C_GRAY, C_WHITE):
            assert isinstance(code, str)
            assert code.startswith("\033[")

    def test_path_constants(self):
        from clashctl.config import (
            CLASH_DIR, CONFIG_YAML, PREFERENCES_JSON,
            SUBSCRIPTIONS_JSON, CUSTOM_RULES_YAML, RULE_PROVIDERS_DIR,
        )
        for p in (CLASH_DIR, CONFIG_YAML, PREFERENCES_JSON,
                  SUBSCRIPTIONS_JSON, CUSTOM_RULES_YAML, RULE_PROVIDERS_DIR):
            assert isinstance(p, str)
            assert len(p) > 0

    def test_default_speedtest_url(self):
        from clashctl.config import DEFAULT_SPEEDTEST_URL
        assert DEFAULT_SPEEDTEST_URL.startswith("http://") or DEFAULT_SPEEDTEST_URL.startswith("https://")

    def test_update_interval(self):
        from clashctl.config import DEFAULT_UPDATE_INTERVAL_HOURS
        assert isinstance(DEFAULT_UPDATE_INTERVAL_HOURS, (int, float))
        assert DEFAULT_UPDATE_INTERVAL_HOURS > 0

    def test_box_width(self):
        from clashctl.config import BOX_W
        assert isinstance(BOX_W, int)
        assert BOX_W > 0

    def test_rule_providers_dict(self):
        from clashctl.config import RULE_PROVIDERS
        assert isinstance(RULE_PROVIDERS, dict)
        for name, cfg in RULE_PROVIDERS.items():
            assert "type" in cfg
            assert "url" in cfg
            assert "path" in cfg

    def test_private_cidrs(self):
        from clashctl.config import PRIVATE_CIDRS
        assert isinstance(PRIVATE_CIDRS, list)
        assert len(PRIVATE_CIDRS) > 0
        for cidr in PRIVATE_CIDRS:
            assert "/" in cidr  # CIDR notation

    def test_uri_type_map(self):
        from clashctl.config import URI_TYPE_MAP
        assert isinstance(URI_TYPE_MAP, dict)
        assert URI_TYPE_MAP["ss"] == "ss"
        assert URI_TYPE_MAP["vmess"] == "vmess"
        assert URI_TYPE_MAP["trojan"] == "trojan"


class TestReadMihomoSecret:
    """Tests for _read_mihomo_secret() and API_SECRET."""

    def test_read_mihomo_secret_returns_string(self):
        from clashctl.config import _read_mihomo_secret
        result = _read_mihomo_secret()
        assert isinstance(result, str)

    def test_read_mihomo_secret_no_file_returns_empty(self, monkeypatch, tmp_path):
        """When config.yaml doesn't exist, should return empty string."""
        from clashctl.config import _read_mihomo_secret
        monkeypatch.setattr(
            "clashctl.config.CLASH_DIR", str(tmp_path)
        )
        result = _read_mihomo_secret()
        assert result == ""

    def test_read_mihomo_secret_with_secret(self, monkeypatch, tmp_path):
        """When config.yaml has a secret field, return it."""
        import yaml
        config_dir = tmp_path
        config_dir.mkdir(parents=True, exist_ok=True)
        cfg_path = config_dir / "config.yaml"
        cfg_path.write_text(yaml.dump({"secret": "my-secret-token"}))

        monkeypatch.setattr("clashctl.config.CLASH_DIR", str(config_dir))

        from clashctl.config import _read_mihomo_secret
        result = _read_mihomo_secret()
        assert result == "my-secret-token"

    def test_read_mihomo_secret_without_secret_field(self, monkeypatch, tmp_path):
        """When config.yaml exists but has no secret field."""
        import yaml
        config_dir = tmp_path
        config_dir.mkdir(parents=True, exist_ok=True)
        cfg_path = config_dir / "config.yaml"
        cfg_path.write_text(yaml.dump({"mixed-port": 7890}))

        monkeypatch.setattr("clashctl.config.CLASH_DIR", str(config_dir))

        from clashctl.config import _read_mihomo_secret
        result = _read_mihomo_secret()
        assert result == ""

    def test_api_secret_env_override(self, monkeypatch):
        """QCG_API_SECRET env var should take priority."""
        monkeypatch.setenv("QCG_API_SECRET", "env-secret-value")
        # Re-import to pick up env var (module-level evaluation)
        import importlib
        import clashctl.config
        importlib.reload(clashctl.config)
        assert clashctl.config.API_SECRET == "env-secret-value"
        # Restore
        monkeypatch.delenv("QCG_API_SECRET", raising=False)
        importlib.reload(clashctl.config)


class TestRulePresets:
    """Verify rule preset structure."""

    def test_rule_presets_exist(self):
        from clashctl.config import RULE_PRESETS
        assert isinstance(RULE_PRESETS, dict)
        assert len(RULE_PRESETS) > 0

    def test_rule_preset_has_required_keys(self):
        from clashctl.config import RULE_PRESETS
        for key, preset in RULE_PRESETS.items():
            assert "name" in preset, f"Preset '{key}' missing 'name'"
            assert "desc" in preset, f"Preset '{key}' missing 'desc'"
            assert "rules" in preset, f"Preset '{key}' missing 'rules'"
            assert isinstance(preset["rules"], list)

    def test_smart_split_preset_exists(self):
        from clashctl.config import RULE_PRESETS
        assert "smart-split" in RULE_PRESETS


class TestDNSPresets:
    """Verify DNS preset structure."""

    def test_dns_presets_exist(self):
        from clashctl.config import DNS_PRESETS
        assert isinstance(DNS_PRESETS, dict)
        assert "fake-ip" in DNS_PRESETS
        assert "redir-host" in DNS_PRESETS

    def test_dns_preset_has_enhanced_mode(self):
        from clashctl.config import DNS_PRESETS
        for key, preset in DNS_PRESETS.items():
            assert "enhanced-mode" in preset

