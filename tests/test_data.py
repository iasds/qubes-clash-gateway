"""Tests for clashctl.data — JSON/YAML I/O and preferences round-trips."""

import json
import os

import pytest

from clashctl.data import (
    load_json,
    save_json,
    load_yaml,
    save_yaml,
    load_preferences,
    save_preferences,
    load_config,
    save_config,
    time_ago,
    uptime_str,
)


# ── Helpers ──────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _patch_data_paths(tmp_path, monkeypatch):
    """Redirect all data I/O to tmp_path so tests don't touch real config."""
    prefs_path = str(tmp_path / "prefs.json")
    subs_path = str(tmp_path / "subs.json")
    config_path = str(tmp_path / "config.yaml")
    custom_rules_path = str(tmp_path / "custom-rules.yaml")
    monkeypatch.setattr("clashctl.data.PREFERENCES_JSON", prefs_path)
    monkeypatch.setattr("clashctl.data.SUBSCRIPTIONS_JSON", subs_path)
    monkeypatch.setattr("clashctl.data.CONFIG_YAML", config_path)
    monkeypatch.setattr("clashctl.data.DEFAULT_SPEEDTEST_URL", "https://www.gstatic.com/generate_204")
    monkeypatch.setattr("clashctl.data.DEFAULT_UPDATE_INTERVAL_HOURS", 6)
    # Also patch the paths where proxy.py might write
    monkeypatch.setattr("clashctl.proxy.CONFIG_YAML", config_path)
    monkeypatch.setattr("clashctl.proxy.CUSTOM_RULES_YAML", custom_rules_path)


# ── load_json / save_json ────────────────────────────────────────────────


class TestJsonIO:
    def test_save_and_load_roundtrip(self, tmp_path):
        path = str(tmp_path / "test.json")
        data = {"key": "value", "number": 42, "nested": {"a": [1, 2, 3]}}
        save_json(path, data)
        loaded = load_json(path)
        assert loaded == data

    def test_load_missing_file_returns_default(self, tmp_path):
        path = str(tmp_path / "nonexistent.json")
        assert load_json(path) == {}
        assert load_json(path, default=[]) == []

    def test_load_corrupt_json_returns_default(self, tmp_path):
        path = str(tmp_path / "bad.json")
        path_obj = tmp_path / "bad.json"
        path_obj.write_text("{invalid json content!!!")
        assert load_json(path) == {}

    def test_save_creates_parent_dirs(self, tmp_path):
        path = str(tmp_path / "subdir" / "nested" / "test.json")
        save_json(path, {"ok": True})
        assert load_json(path) == {"ok": True}

    def test_save_json_atomic(self, tmp_path):
        """save_json should use atomic rename (no .tmp file left behind)."""
        path = str(tmp_path / "atomic.json")
        save_json(path, {"a": 1})
        assert not os.path.exists(path + ".tmp")
        assert os.path.exists(path)


# ── load_yaml / save_yaml ────────────────────────────────────────────────


class TestYamlIO:
    def test_save_and_load_roundtrip(self, tmp_path):
        path = str(tmp_path / "test.yaml")
        data = {
            "mixed-port": 7890,
            "allow-lan": True,
            "proxies": [
                {"name": "node-1", "type": "ss", "server": "1.2.3.4", "port": 443},
            ],
        }
        save_yaml(path, data)
        loaded = load_yaml(path)
        assert loaded == data

    def test_load_missing_file_returns_default(self, tmp_path):
        path = str(tmp_path / "nonexistent.yaml")
        assert load_yaml(path) == {}
        assert load_yaml(path, default={"fallback": True}) == {"fallback": True}

    def test_save_yaml_creates_parent_dirs(self, tmp_path):
        path = str(tmp_path / "a" / "b" / "test.yaml")
        save_yaml(path, {"x": 1})
        assert load_yaml(path) == {"x": 1}

    def test_yaml_preserves_unicode(self, tmp_path):
        path = str(tmp_path / "unicode.yaml")
        data = {"name": "测试节点", "region": "日本"}
        save_yaml(path, data)
        loaded = load_yaml(path)
        assert loaded["name"] == "测试节点"
        assert loaded["region"] == "日本"


# ── load_config / save_config ────────────────────────────────────────────


class TestConfigIO:
    def test_roundtrip(self):
        config = {
            "mixed-port": 7890,
            "mode": "rule",
            "proxies": [{"name": "test", "type": "ss"}],
        }
        save_config(config)
        loaded = load_config()
        assert loaded == config

    def test_load_empty_returns_empty_dict(self):
        """When no config file exists, load_config returns {}."""
        result = load_config()
        assert isinstance(result, dict)

    def test_overwrite_config(self):
        save_config({"mode": "rule"})
        save_config({"mode": "global", "allow-lan": True})
        loaded = load_config()
        assert loaded["mode"] == "global"
        assert loaded["allow-lan"] is True


# ── load_preferences / save_preferences ──────────────────────────────────


class TestPreferencesIO:
    def test_defaults_populated(self):
        prefs = load_preferences()
        assert "mode" in prefs
        assert "rule_preset" in prefs
        assert "dns_preset" in prefs
        assert "global_node" in prefs
        assert "language" in prefs
        assert "history" in prefs

    def test_roundtrip(self):
        prefs = load_preferences()
        prefs["mode"] = "global"
        prefs["selected_node"] = "fast-node"
        save_preferences(prefs)
        loaded = load_preferences()
        assert loaded["mode"] == "global"
        assert loaded["selected_node"] == "fast-node"

    def test_defaults_fill_missing_keys(self):
        """Saved prefs missing new keys should get defaults filled in."""
        minimal = {"mode": "direct"}
        save_preferences(minimal)
        loaded = load_preferences()
        assert loaded["mode"] == "direct"
        # Defaults should be present
        assert "rule_preset" in loaded
        assert "dns_preset" in loaded
        assert "history" in loaded

    def test_no_file_returns_defaults(self):
        prefs = load_preferences()
        assert prefs["mode"] == "rule"
        assert prefs["rule_preset"] == "smart-split"
        assert prefs["dns_preset"] == "fake-ip"
        assert prefs["language"] == "zh"


# ── time_ago / uptime_str ───────────────────────────────────────────────


class TestFormatters:
    def test_time_ago_none(self):
        assert time_ago(None) == "never"
        assert time_ago("") == "never"

    def test_time_ago_recent(self):
        from datetime import datetime
        now = datetime.now().isoformat()
        result = time_ago(now)
        assert "s ago" in result or "m ago" in result

    def test_uptime_str_zero(self):
        assert uptime_str(0) == "0m"

    def test_uptime_str_hours(self):
        result = uptime_str(3661)  # 1h 1m 1s
        assert "h" in result
        assert "m" in result

    def test_uptime_str_negative(self):
        assert uptime_str(-1) == "N/A"

    def test_uptime_str_minutes_only(self):
        result = uptime_str(300)  # 5 minutes
        assert result == "5m"
