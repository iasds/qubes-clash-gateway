"""Subscription parser for Clash YAML, V2Ray/SS/SSR/Trojan/Hysteria2 URIs.

Parses subscription URLs and raw URI strings into mihomo proxy config dicts.
Supports:
  - Clash YAML (base64 or plain)
  - vmess:// (V2Ray)
  - ss:// (Shadowsocks, base64 or SIP002)
  - ssr:// (ShadowsocksR)
  - trojan://
  - hysteria2:// / hy2://
  - tuic://
  - anytls://
"""

import base64
import json
import urllib.request
import urllib.error
import re
from typing import Optional
from urllib.parse import urlparse, parse_qs, unquote


# ── Fetch subscription URL ────────────────────────────────────────────────

def fetch_subscription(url: str, timeout: int = 15) -> str:
    """Fetch subscription content from URL. Returns raw text."""
    req = urllib.request.Request(url, headers={
        "User-Agent": "clash-verge/v2.0.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


# ── Base64 helpers ────────────────────────────────────────────────────────

def _try_base64(s: str) -> str:
    """Try to decode base64, return original if fails."""
    # Add padding if needed
    s = s.strip()
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    try:
        return base64.b64decode(s).decode("utf-8")
    except Exception:
        return s


# ── URI parsers ───────────────────────────────────────────────────────────

def _parse_vmess(uri: str) -> Optional[dict]:
    """Parse vmess:// URI (V2RayN format, base64-encoded JSON)."""
    if not uri.startswith("vmess://"):
        return None
    try:
        raw = _try_base64(uri[8:])
        data = json.loads(raw)
        name = data.get("ps", data.get("name", "vmess-node"))
        # Clean name
        name = re.sub(r'^\[.*?\]\s*', '', name).strip() or "vmess-node"

        proxy = {
            "name": name,
            "type": "vmess",
            "server": data.get("add", ""),
            "port": int(data.get("port", 443)),
            "uuid": data.get("id", ""),
            "alterId": int(data.get("aid", 0)),
            "cipher": data.get("scy", "auto"),
            "udp": True,
        }

        # TLS
        tls = data.get("tls", "")
        if tls == "tls":
            proxy["tls"] = True
            sni = data.get("sni") or data.get("host") or ""
            if sni:
                proxy["servername"] = sni

        # Transport
        net = data.get("net", "tcp")
        if net == "ws":
            proxy["network"] = "ws"
            proxy["ws-opts"] = {
                "path": data.get("path", "/"),
                "headers": {"Host": data.get("host", "")},
            }
        elif net == "grpc":
            proxy["network"] = "grpc"
            proxy["grpc-opts"] = {"grpc-service-name": data.get("path", "")}
        elif net == "h2":
            proxy["network"] = "h2"
            proxy["h2-opts"] = {
                "host": [data.get("host", "")],
                "path": data.get("path", "/"),
            }

        return proxy
    except Exception:
        return None


def _parse_ss(uri: str) -> Optional[dict]:
    """Parse ss:// URI (Shadowsocks, base64 or SIP002 format)."""
    if not uri.startswith("ss://"):
        return None
    try:
        body = uri[5:]
        name = ""

        # SIP002 format: ss://base64(method:password)@server:port#name
        if "@" in body and not body.startswith("YW"):
            # Likely SIP002
            userinfo, serverinfo = body.split("@", 1)
            if "#" in serverinfo:
                serverinfo, name = serverinfo.split("#", 1)
                name = unquote(name)

            # userinfo might be base64
            decoded_userinfo = _try_base64(userinfo)
            if ":" in decoded_userinfo:
                method, password = decoded_userinfo.split(":", 1)
            else:
                method, password = "aes-256-gcm", userinfo

            if ":" in serverinfo:
                server, port = serverinfo.rsplit(":", 1)
                # Remove query params
                if "?" in port:
                    port = port.split("?")[0]
                port = int(port)
            else:
                server, port = serverinfo, 443

        else:
            # Standard base64 format: ss://base64(method:password@server:port)#name
            if "#" in body:
                body, name = body.split("#", 1)
                name = unquote(name)
            decoded = _try_base64(body)
            # method:password@server:port
            if "@" in decoded:
                method_pass, server_port = decoded.rsplit("@", 1)
                method, password = method_pass.split(":", 1)
                server, port = server_port.rsplit(":", 1)
                port = int(port)
            else:
                return None

        name = name or f"ss-{server}"
        return {
            "name": name,
            "type": "ss",
            "server": server,
            "port": port,
            "cipher": method,
            "password": password,
            "udp": True,
        }
    except Exception:
        return None


def _parse_ssr(uri: str) -> Optional[dict]:
    """Parse ssr:// URI (ShadowsocksR)."""
    if not uri.startswith("ssr://"):
        return None
    try:
        decoded = _try_base64(uri[6:])
        # SSR format: server:port:protocol:method:obfs:base64pass/?params
        main_part = decoded.split("/?")[0]
        parts = main_part.split(":")
        if len(parts) < 6:
            return None

        server, port, protocol, method, obfs, password_b64 = parts[:6]
        password = _try_base64(password_b64)

        # Parse params
        params = {}
        if "/?" in decoded:
            param_str = decoded.split("/?")[1]
            for p in param_str.split("&"):
                if "=" in p:
                    k, v = p.split("=", 1)
                    params[k] = _try_base64(v)

        name = params.get("remarks", "")
        if not name:
            name = _try_base64(params.get("group", "")) or f"ssr-{server}"

        return {
            "name": name,
            "type": "ss",
            "server": server,
            "port": int(port),
            "cipher": method,
            "password": password,
            "udp": True,
        }
    except Exception:
        return None


def _parse_trojan(uri: str) -> Optional[dict]:
    """Parse trojan:// URI."""
    if not uri.startswith("trojan://"):
        return None
    try:
        parsed = urlparse(uri)
        name = unquote(parsed.fragment) if parsed.fragment else f"trojan-{parsed.hostname}"

        proxy = {
            "name": name,
            "type": "trojan",
            "server": parsed.hostname,
            "port": parsed.port or 443,
            "password": parsed.username or unquote(parsed.password or ""),
            "udp": True,
        }

        params = parse_qs(parsed.query)
        if "sni" in params:
            proxy["sni"] = params["sni"][0]
        if "peer" in params:
            proxy["sni"] = params["peer"][0]

        return proxy
    except Exception:
        return None


def _parse_hysteria2(uri: str) -> Optional[dict]:
    """Parse hysteria2:// or hy2:// URI."""
    if not (uri.startswith("hysteria2://") or uri.startswith("hy2://")):
        return None
    try:
        # hy2://password@server:port?params#name
        if uri.startswith("hy2://"):
            uri = "hysteria2://" + uri[6:]
        parsed = urlparse(uri)
        name = unquote(parsed.fragment) if parsed.fragment else f"hy2-{parsed.hostname}"

        proxy = {
            "name": name,
            "type": "hysteria2",
            "server": parsed.hostname,
            "port": parsed.port or 443,
            "password": parsed.username or unquote(parsed.password or ""),
            "udp": True,
        }

        params = parse_qs(parsed.query)
        if "sni" in params:
            proxy["sni"] = params["sni"][0]
        if "insecure" in params:
            proxy["skip-cert-verify"] = params["insecure"][0] == "1"

        return proxy
    except Exception:
        return None


def _parse_tuic(uri: str) -> Optional[dict]:
    """Parse tuic:// URI."""
    if not uri.startswith("tuic://"):
        return None
    try:
        parsed = urlparse(uri)
        name = unquote(parsed.fragment) if parsed.fragment else f"tuic-{parsed.hostname}"

        # tuic://uuid:password@server:port#name
        proxy = {
            "name": name,
            "type": "tuic",
            "server": parsed.hostname,
            "port": parsed.port or 443,
            "uuid": parsed.username or "",
            "password": parsed.password or "",
            "udp": True,
        }

        params = parse_qs(parsed.query)
        if "sni" in params:
            proxy["sni"] = params["sni"][0]

        return proxy
    except Exception:
        return None


# ── Dispatch ──────────────────────────────────────────────────────────────

def parse_uri(uri: str) -> Optional[dict]:
    """Parse a single proxy URI into a mihomo proxy config dict."""
    uri = uri.strip()
    if not uri:
        return None

    parsers = [
        _parse_vmess,
        _parse_ssr,  # before ss:// since ssr:// starts differently
        _parse_ss,
        _parse_trojan,
        _parse_hysteria2,
        _parse_tuic,
    ]

    for parser in parsers:
        result = parser(uri)
        if result:
            return result

    return None


def parse_subscription_text(text: str) -> list[dict]:
    """Parse subscription text (could be Clash YAML, base64 URIs, or raw URIs)."""
    text = text.strip()
    if not text:
        return []

    # Try Clash YAML first
    try:
        import yaml
        data = yaml.safe_load(text)
        if isinstance(data, dict) and "proxies" in data:
            return [p for p in data["proxies"] if isinstance(p, dict)]
    except Exception:
        pass

    # Try base64 decode (common subscription format)
    decoded = _try_base64(text)
    if decoded != text and ("\n" in decoded or "://" in decoded):
        text = decoded

    # Parse line by line
    proxies = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "://" in line:
            proxy = parse_uri(line)
            if proxy:
                proxies.append(proxy)

    return proxies


def parse_subscription(url: str) -> list[dict]:
    """Fetch and parse a subscription URL."""
    text = fetch_subscription(url)
    return parse_subscription_text(text)
