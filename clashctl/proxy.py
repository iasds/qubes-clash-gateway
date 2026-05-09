"""YAML config operations + API calls for mihomo (Clash Meta)

Reads/writes the mihomo config.yaml, applies mode presets (rule/global/direct),
DNS presets, manages custom rules, and generates the full mihomo config.
"""
import os
import subprocess
import urllib.request
import urllib.error
from typing import Optional

from .config import (
    CONFIG_YAML,
    CUSTOM_RULES_YAML,
    RULE_PRESETS,
    DNS_PRESETS,
    RULE_PROVIDERS,
    PRIVATE_CIDRS,
    C_GREEN,
    C_RED,
    C_CYAN,
    C_DIM,
    C_RESET,
    API_BASE,
    API_PORT,
    API_SECRET,
)
from .data import load_config, save_config, load_yaml, save_yaml, load_preferences, save_preferences
from .api import ClashAPI, ClashAPIError


# ── Helpers ──────────────────────────────────────────────────────────────────

def _api() -> ClashAPI:
    """Return a fresh ClashAPI instance."""
    return ClashAPI()


def _get_proxies_list(cfg: dict) -> list[str]:
    """Extract all proxy node names from the config."""
    return [p.get("name", "") for p in cfg.get("proxies", []) if p.get("name")]


def _make_auto_group(proxies_list: list[str]) -> dict:
    """Create a urltest auto proxy-group."""
    return {
        "name": "auto",
        "type": "url-test",
        "proxies": proxies_list,
        "url": "https://www.gstatic.com/generate_204",
        "interval": 300,
        "tolerance": 50,
    }


def _make_select_group(proxies_list: list[str]) -> dict:
    """Create a select proxy-group with all nodes + auto."""
    return {
        "name": "GLOBAL",
        "type": "select",
        "proxies": ["auto"] + proxies_list,
    }


def _build_base_config() -> dict:
    """Return the skeleton mihomo config (no proxies/rules yet)."""
    return {
        "mixed-port": 7890,
        "allow-lan": False,
        "bind-address": "*",
        "mode": "rule",
        "log-level": "info",
        "ipv6": False,
        "tcp-concurrent": True,
        "find-process-mode": "off",
        "global-client-fingerprint": "chrome",
        "tun": {
            "enable": True,
            "stack": "system",
            # Key: don't use auto-redirect and dns-hijack
            # Manually use nftables to hijack AppVM traffic, avoiding mihomo's own DNS loop
            "auto-route": True,
            "auto-redirect": False,
            "auto-detect-interface": True,
            "mtu": 9000,
            "strict-route": False,
            "route-exclude-address": [
                "10.0.0.0/8",
                "172.16.0.0/12",
                "192.168.0.0/16",
            ],
        },
        "dns": {},
        "proxies": [],
        "proxy-groups": [],
        "rules": [],
        "rule-providers": {},
    }


# ── Process / status ─────────────────────────────────────────────────────────

def is_running() -> bool:
    """Check whether mihomo is running by hitting its version endpoint."""
    try:
        api = _api()
        api.version()
        return True
    except (ClashAPIError, Exception):
        return False


def get_exit_ip() -> Optional[str]:
    """Return the exit IP address seen by the outside world.

    Routes the request through the mihomo mixed-port proxy so the returned
    IP is the proxy exit IP, not the local gateway IP.
    """
    from .nodes import get_exit_ip as _get_exit_ip
    try:
        from .api import ClashAPI
        api = ClashAPI()
        result = _get_exit_ip(api, timeout=8)
        return None if result == "Unknown" else result
    except Exception:
        return None


def restart() -> bool:
    """Restart mihomo via systemctl.  Returns True on success."""
    try:
        subprocess.run(
            ["sudo", "systemctl", "restart", "mihomo"],
            check=True,
            capture_output=True,
            timeout=15,
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return False


# ── Mode detection & switching ───────────────────────────────────────────────

def detect_current_mode() -> str:
    """Detect the current proxy mode from the running mihomo instance.

    Returns 'rule', 'global', or 'direct'.  Falls back to the config on disk.
    """
    try:
        api = _api()
        return api.get_mode()
    except (ClashAPIError, Exception):
        cfg = load_config()
        return cfg.get("mode", "rule")


def apply_mode(mode: str, rule_preset: Optional[str] = None) -> bool:
    """Apply a proxy mode by rewriting the YAML config and restarting mihomo.

    Args:
        mode: 'rule', 'global', or 'direct'.
        rule_preset: Key into RULE_PRESETS (default: smart-split for rule mode).

    Returns True on success.
    """
    if mode not in ("rule", "global", "direct"):
        return False

    cfg = load_config()
    if not cfg:
        cfg = _build_base_config()

    proxies_list = _get_proxies_list(cfg)
    cfg["mode"] = mode

    if mode == "global":
        # Keep a select group with all nodes so the user can pick manually
        cfg["proxy-groups"] = [_make_auto_group(proxies_list), _make_select_group(proxies_list)]
        cfg["rules"] = ["GEOIP,private,DIRECT", "MATCH,GLOBAL"]

    elif mode == "rule":
        # url-test auto group for best-node selection
        cfg["proxy-groups"] = [_make_auto_group(proxies_list)]
        preset_key = rule_preset or "smart-split"
        preset = RULE_PRESETS.get(preset_key, RULE_PRESETS.get("smart-split"))
        cfg["rules"] = list(preset.get("rules", []))

    elif mode == "direct":
        # Remove all proxy groups; everything goes DIRECT
        cfg["proxy-groups"] = []
        cfg["rules"] = [
            "GEOIP,private,DIRECT",
            "MATCH,DIRECT",
        ]

    # Ensure rule-providers are present
    cfg["rule-providers"] = dict(RULE_PROVIDERS)

    save_config(cfg)

    # Apply via API if running, otherwise restart the service
    try:
        api = _api()
        api.reload(CONFIG_YAML)
    except (ClashAPIError, Exception):
        restart()

    # Persist preference
    prefs = load_preferences()
    prefs["mode"] = mode
    if rule_preset:
        prefs["rule_preset"] = rule_preset
    save_preferences(prefs)

    return True


# ── Proxy node management ────────────────────────────────────────────────────

def clear_proxy_nodes() -> bool:
    """Remove all proxy nodes and proxy-groups from the config.

    The mihomo process is restarted after clearing.
    """
    cfg = load_config()
    cfg["proxies"] = []
    cfg["proxy-groups"] = []
    cfg["rules"] = ["GEOIP,private,DIRECT", "MATCH,DIRECT"]
    save_config(cfg)
    try:
        api = _api()
        api.reload(CONFIG_YAML)
    except (ClashAPIError, Exception):
        restart()
    return True


# ── DNS ──────────────────────────────────────────────────────────────────────

def get_current_dns() -> dict:
    """Return the current DNS configuration from the config on disk."""
    cfg = load_config()
    return cfg.get("dns", {})


def apply_dns_preset(preset_key: str) -> bool:
    """Apply a DNS preset to the mihomo config.

    Args:
        preset_key: Key into DNS_PRESETS (e.g. 'fake-ip', 'redir-host').

    Returns True on success.
    """
    preset = DNS_PRESETS.get(preset_key)
    if not preset:
        return False

    cfg = load_config()
    if not cfg:
        cfg = _build_base_config()

    dns: dict = {
        "enable": True,
        "enhanced-mode": preset.get("enhanced-mode", "fake-ip"),
        "nameserver": list(preset.get("nameserver", [])),
        "fallback": list(preset.get("fallback", [])),
        "fallback-filter": dict(preset.get("fallback-filter", {})),
    }

    if preset.get("enhanced-mode") == "fake-ip":
        dns["fake-ip-range"] = preset.get("fake-ip-range", "198.18.0.1/16")
        dns["fake-ip-filter"] = list(preset.get("fake-ip-filter", []))

    cfg["dns"] = dns
    save_config(cfg)

    # Persist preference
    prefs = load_preferences()
    prefs["dns_preset"] = preset_key
    save_preferences(prefs)

    try:
        api = _api()
        api.reload(CONFIG_YAML)
    except (ClashAPIError, Exception):
        restart()

    return True


# ── Custom rules ─────────────────────────────────────────────────────────────

def load_custom_rules() -> list[dict]:
    """Load custom rules from the persistent YAML file.

    Each entry is a dict with keys: 'type', 'payload', 'target'.
    Example: {"type": "DOMAIN-SUFFIX", "payload": "example.com", "target": "auto"}
    """
    rules = load_yaml(CUSTOM_RULES_YAML, [])
    if not isinstance(rules, list):
        return []
    return rules


def _save_custom_rules(rules: list[dict]) -> None:
    """Persist custom rules to the YAML file."""
    save_yaml(CUSTOM_RULES_YAML, rules)


def add_custom_rule(rule_type: str, payload: str, target: str = "auto") -> bool:
    """Append a custom rule.

    Args:
        rule_type: mihomo rule type (DOMAIN, DOMAIN-SUFFIX, IP-CIDR, etc.).
        payload:   The match value.
        target:    Proxy group or DIRECT/REJECT (default 'auto').

    Returns True if added, False if duplicate.
    """
    rules = load_custom_rules()
    # Check for duplicates
    for r in rules:
        if r.get("type") == rule_type and r.get("payload") == payload:
            return False
    rules.append({"type": rule_type, "payload": payload, "target": target})
    _save_custom_rules(rules)
    return True


def remove_custom_rule(rule_type: str, payload: str) -> bool:
    """Remove a custom rule by type and payload.

    Returns True if removed, False if not found.
    """
    rules = load_custom_rules()
    before = len(rules)
    rules = [
        r for r in rules
        if not (r.get("type") == rule_type and r.get("payload") == payload)
    ]
    if len(rules) == before:
        return False
    _save_custom_rules(rules)
    return True


# ── Full config generation ───────────────────────────────────────────────────

def generate_full_config(
    proxies: Optional[list[dict]] = None,
    mode: str = "rule",
    rule_preset: str = "smart-split",
    dns_preset: str = "fake-ip",
) -> dict:
    """Generate a complete mihomo config dict from scratch.

    Args:
        proxies:     List of proxy node dicts (mihomo proxy format).
        mode:        'rule', 'global', or 'direct'.
        rule_preset: Key into RULE_PRESETS.
        dns_preset:  Key into DNS_PRESETS.

    Returns:
        A complete mihomo config dict ready to be saved.
    """
    cfg = _build_base_config()
    cfg["mode"] = mode

    # Proxies
    proxies = proxies or []
    cfg["proxies"] = proxies
    names = [p.get("name", "") for p in proxies if p.get("name")]

    # Proxy-groups
    if mode == "global":
        cfg["proxy-groups"] = [_make_auto_group(names), _make_select_group(names)]
    elif mode == "rule":
        cfg["proxy-groups"] = [_make_auto_group(names)]
    else:
        cfg["proxy-groups"] = []

    # Rules
    if mode == "direct":
        cfg["rules"] = ["GEOIP,private,DIRECT", "MATCH,DIRECT"]
    elif mode == "global":
        cfg["rules"] = ["GEOIP,private,DIRECT", "MATCH,GLOBAL"]
    else:
        preset = RULE_PRESETS.get(rule_preset, RULE_PRESETS.get("smart-split"))
        cfg["rules"] = list(preset.get("rules", []))

    # Custom rules — inject before MATCH
    custom = load_custom_rules()
    if custom and cfg["rules"]:
        match_idx = None
        for i, rule in enumerate(cfg["rules"]):
            if rule.startswith("MATCH"):
                match_idx = i
                break
        custom_strs = [f"{c['type']},{c['payload']},{c['target']}" for c in custom]
        if match_idx is not None:
            cfg["rules"] = cfg["rules"][:match_idx] + custom_strs + cfg["rules"][match_idx:]
        else:
            cfg["rules"].extend(custom_strs)

    # Rule-providers
    cfg["rule-providers"] = dict(RULE_PROVIDERS)

    # DNS
    dns_preset_data = DNS_PRESETS.get(dns_preset, DNS_PRESETS.get("fake-ip"))
    dns: dict = {
        "enable": True,
        "enhanced-mode": dns_preset_data.get("enhanced-mode", "fake-ip"),
        "nameserver": list(dns_preset_data.get("nameserver", [])),
        "fallback": list(dns_preset_data.get("fallback", [])),
        "fallback-filter": dict(dns_preset_data.get("fallback-filter", {})),
    }
    if dns_preset_data.get("enhanced-mode") == "fake-ip":
        dns["fake-ip-range"] = dns_preset_data.get("fake-ip-range", "198.18.0.1/16")
        dns["fake-ip-filter"] = list(dns_preset_data.get("fake-ip-filter", []))
    cfg["dns"] = dns

    return cfg


def apply_full_config(proxies: Optional[list[dict]] = None, **kwargs) -> bool:
    """Generate, save, and apply a full mihomo config.

    Accepts the same keyword arguments as generate_full_config().
    Returns True on success.
    """
    cfg = generate_full_config(proxies=proxies, **kwargs)
    save_config(cfg)
    try:
        api = _api()
        api.reload(CONFIG_YAML)
    except (ClashAPIError, Exception):
        restart()

    # Persist preferences
    prefs = load_preferences()
    prefs["mode"] = kwargs.get("mode", "rule")
    prefs["rule_preset"] = kwargs.get("rule_preset", "smart-split")
    prefs["dns_preset"] = kwargs.get("dns_preset", "fake-ip")
    save_preferences(prefs)

    return True
