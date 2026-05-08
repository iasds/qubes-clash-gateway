"""JSON/YAML file I/O and preferences management"""
import json
import os
from datetime import datetime
from .config import (
    PREFERENCES_JSON, SUBSCRIPTIONS_JSON, CONFIG_YAML,
    DEFAULT_SPEEDTEST_URL, DEFAULT_UPDATE_INTERVAL_HOURS,
)


def load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default if default is not None else {}


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def load_yaml(path, default=None):
    """Load YAML config (requires pyyaml)"""
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or (default if default is not None else {})
    except (FileNotFoundError, ImportError):
        return default if default is not None else {}


def save_yaml(path, data):
    """Save YAML config (requires pyyaml)"""
    try:
        import yaml
    except ImportError:
        raise ImportError("PyYAML is required to save YAML files. Install with: pip install pyyaml")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    os.replace(tmp, path)


def load_preferences():
    defaults = {
        "mode": "rule",
        "rule_preset": "smart-split",
        "dns_preset": "fake-ip",
        "global_node": None,
        "last_update": None,
        "update_interval_hours": DEFAULT_UPDATE_INTERVAL_HOURS,
        "speedtest_url": DEFAULT_SPEEDTEST_URL,
        "language": "zh",
        "history": [],
    }
    prefs = load_json(PREFERENCES_JSON, defaults)
    for k, v in defaults.items():
        if k not in prefs:
            prefs[k] = v
    return prefs


def save_preferences(prefs):
    save_json(PREFERENCES_JSON, prefs)


def load_config():
    return load_yaml(CONFIG_YAML, {})


def save_config(config):
    save_yaml(CONFIG_YAML, config)


def load_subscriptions():
    return load_json(SUBSCRIPTIONS_JSON, {"subscriptions": []})


def save_subscriptions(subs):
    save_json(SUBSCRIPTIONS_JSON, subs)


def time_ago(iso_str):
    if not iso_str:
        return "从未"
    try:
        dt = datetime.fromisoformat(iso_str)
        diff = datetime.now() - dt
        secs = int(diff.total_seconds())
        if secs < 60:
            return f"{secs}秒前"
        if secs < 3600:
            return f"{secs // 60}分钟前"
        if secs < 86400:
            return f"{secs // 3600}h前"
        return f"{secs // 86400}天前"
    except Exception:
        return "未知"


def uptime_str(secs):
    if secs < 0:
        return "N/A"
    h, m = divmod(secs // 60, 60)
    if h > 0:
        return f"{h}h{m}m"
    return f"{m}m"
