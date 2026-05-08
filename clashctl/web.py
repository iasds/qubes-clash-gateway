"""Lightweight web UI for qubes-clash-gateway.

Pure Python stdlib (http.server + threading), zero dependencies.
Start with: clashctl web   OR   python -m clashctl web
Binds to 127.0.0.1:9091 by default.
"""

import json
import os
import sys
import subprocess
from datetime import datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Any

from .config import (
    API_BASE, API_PORT, API_SECRET,
    CONFIG_YAML, SUBSCRIPTIONS_JSON,
)
from .api import ClashAPI, ClashAPIError

# ── Constants ───────────────────────────────────────────────────────────────

WEB_HOST = "127.0.0.1"
WEB_PORT = 9091

_WEB_SECRET = ""  # Set via run_server(); empty = no auth

_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "web_templates")
_TEMPLATE_PATH = os.path.join(_TEMPLATE_DIR, "index.html")

_GROUP_TYPES = frozenset({
    "Selector", "URLTest", "Fallback", "LoadBalance",
    "Relay", "Compatible", "Fallback-UD",
})
_VIRTUAL = frozenset({"DIRECT", "REJECT", "GLOBAL", "PASS"})


# ── Helpers ─────────────────────────────────────────────────────────────────

def _api() -> ClashAPI:
    return ClashAPI()


def _json(handler, data: Any, status: int = 200):
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(body)


def _err(handler, msg: str, status: int = 400):
    _json(handler, {"error": msg}, status)


def _read_body(handler) -> dict:
    length = int(handler.headers.get("Content-Length", 0))
    if not length:
        return {}
    try:
        return json.loads(handler.rfile.read(length).decode("utf-8"))
    except Exception:
        return {}


def _load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default if default is not None else {}


def _save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def _load_yaml(path, default=None):
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or (default if default is not None else {})
    except (FileNotFoundError, ImportError):
        return default if default is not None else {}


def _save_yaml(path, data):
    import yaml
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    os.replace(tmp, path)


def _time_ago(iso_str):
    if not iso_str:
        return "never"
    try:
        dt = datetime.fromisoformat(iso_str)
        secs = int((datetime.now() - dt).total_seconds())
        if secs < 60:
            return f"{secs}s ago"
        if secs < 3600:
            return f"{secs // 60}m ago"
        if secs < 86400:
            return f"{secs // 3600}h ago"
        return f"{secs // 86400}d ago"
    except Exception:
        return "unknown"


# ── HTML ────────────────────────────────────────────────────────────────────

_HTML_CACHE = None
_HTML_CACHE_MTIME = 0.0  # file mtime when cached

def _get_html() -> str:
    global _HTML_CACHE, _HTML_CACHE_MTIME
    try:
        mtime = os.path.getmtime(_TEMPLATE_PATH)
    except OSError:
        mtime = 0
    if _HTML_CACHE is None or mtime != _HTML_CACHE_MTIME:
        with open(_TEMPLATE_PATH, encoding="utf-8") as f:
            _HTML_CACHE = f.read()
        _HTML_CACHE_MTIME = mtime
    return _HTML_CACHE


# ── API Logic ───────────────────────────────────────────────────────────────

def api_status():
    running = False
    version = ""
    mode = "rule"
    try:
        api = _api()
        version = api.version().get("version", "")
        running = True
        mode = api.get_mode()
    except Exception:
        cfg = _load_yaml(CONFIG_YAML, {})
        mode = cfg.get("mode", "rule")

    exit_ip = ""
    try:
        from .nodes import get_exit_ip
        exit_ip = get_exit_ip(api if running else None, timeout=5)
        if exit_ip == "Unknown":
            exit_ip = ""
    except Exception:
        pass

    node_count = 0
    conn_count = 0
    if running:
        try:
            data = api.get_proxies()
            for name, info in data.get("proxies", {}).items():
                if name not in _VIRTUAL and info.get("type") not in _GROUP_TYPES:
                    node_count += 1
        except Exception:
            pass
        try:
            conn_count = len(api.get_connections().get("connections", []))
        except Exception:
            pass

    return {
        "running": running,
        "version": version,
        "mode": mode,
        "exit_ip": exit_ip,
        "node_count": node_count,
        "connection_count": conn_count,
    }


def api_nodes():
    try:
        api = _api()
        data = api.get_proxies()
        groups = []
        for name, info in data.get("proxies", {}).items():
            if info.get("type") in _GROUP_TYPES:
                members = [m for m in info.get("all", []) if m not in _VIRTUAL]
                groups.append({
                    "name": name,
                    "type": info.get("type", ""),
                    "current": info.get("now", ""),
                    "members": members,
                })
        return {"groups": groups}
    except Exception as e:
        return {"groups": [], "error": str(e)}


def api_switch_node(body):
    group = body.get("group", "")
    name = body.get("name", "")
    if not group or not name:
        return {"error": "group and name required"}
    try:
        _api().switch_proxy(group, name)
        return {"ok": True}
    except Exception as e:
        return {"error": str(e)}


def api_connections():
    try:
        api = _api()
        data = api.get_connections()
        conns = []
        for c in data.get("connections", []):
            meta = c.get("metadata", {})
            conns.append({
                "id": c.get("id", ""),
                "metadata": {
                    "network": meta.get("network", "tcp"),
                    "host": meta.get("host", ""),
                    "destinationIP": meta.get("destinationIP", ""),
                    "destinationPort": meta.get("destinationPort", ""),
                    "sourceIP": meta.get("sourceIP", ""),
                },
                "chains": c.get("chains", []),
                "upload": c.get("upload", 0),
                "download": c.get("download", 0),
            })
        return {"connections": conns}
    except Exception as e:
        return {"connections": [], "error": str(e)}


def api_close_conn(conn_id):
    try:
        _api().close_connection(conn_id)
        return {"ok": True}
    except Exception as e:
        return {"error": str(e)}


def api_close_all():
    try:
        _api().close_all_connections()
        return {"ok": True}
    except Exception as e:
        return {"error": str(e)}


def api_set_mode(body):
    mode = body.get("mode", "")
    if mode not in ("rule", "global", "direct"):
        return {"error": "invalid mode"}
    try:
        api = _api()
        api.mode(mode)
        return {"ok": True, "mode": mode}
    except Exception as e:
        # Fallback: try full config rebuild
        try:
            from .proxy import apply_mode
            return {"ok": apply_mode(mode), "mode": mode, "fallback": True}
        except Exception as e2:
            return {"error": f"API: {e}; fallback: {e2}"}


def api_subscriptions():
    subs = _load_json(SUBSCRIPTIONS_JSON, {"subscriptions": []})
    for s in subs.get("subscriptions", []):
        s["last_update_ago"] = _time_ago(s.get("last_update"))
    return subs


def api_add_subscription(body):
    from .parser import parse_subscription
    url = body.get("url", "")
    if not url:
        return {"error": "url required"}
    # Basic URL validation to prevent SSRF
    if not url.startswith(("http://", "https://")):
        return {"error": "Only http/https URLs are allowed"}
    try:
        proxies = parse_subscription(url)
    except Exception as e:
        return {"error": f"parse failed: {e}"}
    if not proxies:
        return {"error": "empty subscription"}

    name = f"sub-{datetime.now().strftime('%m%d%H%M')}"
    subs = _load_json(SUBSCRIPTIONS_JSON, {"subscriptions": []})
    subs["subscriptions"].append({
        "name": name, "url": url,
        "proxy_count": len(proxies),
        "last_update": datetime.now().isoformat(),
    })
    _save_json(SUBSCRIPTIONS_JSON, subs)

    cfg = _load_yaml(CONFIG_YAML, {})
    existing = cfg.get("proxies", [])
    existing_names = {p.get("name") for p in existing}
    added = 0
    for p in proxies:
        if p.get("name") not in existing_names:
            existing.append(p)
            existing_names.add(p.get("name"))
            added += 1
    cfg["proxies"] = existing
    _save_yaml(CONFIG_YAML, cfg)

    return {"ok": True, "count": len(proxies), "added": added}


def api_remove_subscription(index):
    subs = _load_json(SUBSCRIPTIONS_JSON, {"subscriptions": []})
    sub_list = subs.get("subscriptions", [])
    if 0 <= index < len(sub_list):
        sub_list.pop(index)
        subs["subscriptions"] = sub_list
        _save_json(SUBSCRIPTIONS_JSON, subs)
        return {"ok": True}
    return {"error": "invalid index"}


def api_update_subscriptions():
    from .parser import parse_subscription
    from .proxy import detect_current_mode, apply_mode
    subs = _load_json(SUBSCRIPTIONS_JSON, {"subscriptions": []})
    sub_list = subs.get("subscriptions", [])
    if not sub_list:
        return {"ok": True, "message": "no subscriptions"}
    cfg = _load_yaml(CONFIG_YAML, {})
    all_new = []
    for s in sub_list:
        try:
            proxies = parse_subscription(s["url"])
            all_new.extend(proxies)
            s["proxy_count"] = len(proxies)
            s["last_update"] = datetime.now().isoformat()
        except Exception:
            pass
    if all_new:
        cfg["proxies"] = all_new
        _save_yaml(CONFIG_YAML, cfg)
        _save_json(SUBSCRIPTIONS_JSON, subs)
        try:
            apply_mode(detect_current_mode())
        except Exception:
            pass
    return {"ok": True, "total": len(all_new)}


def api_restart():
    try:
        subprocess.run(["sudo", "systemctl", "restart", "mihomo"], check=True, timeout=15)
        return {"ok": True}
    except Exception as e:
        return {"error": str(e)}


def api_flush_dns():
    try:
        _api().flush_dns_cache()
        return {"ok": True}
    except Exception as e:
        return {"error": str(e)}


def api_flush_fakeip():
    try:
        _api().flush_fake_ip_cache()
        return {"ok": True}
    except Exception as e:
        return {"error": str(e)}


def api_speed_test(body):
    """Run latency test for nodes in a group, or all groups."""
    group = body.get("group", "")
    try:
        api = _api()
        from .nodes import speed_test, get_group_nodes, get_proxy_groups, NodeInfo

        if group:
            nodes = get_group_nodes(api, group)
        else:
            # Test all nodes from all groups
            groups = get_proxy_groups(api)
            seen = set()
            nodes = []
            for g in groups:
                for m in g.members:
                    if m not in seen:
                        seen.add(m)
                        nodes.append(NodeInfo(name=m, type=""))

        if not nodes:
            return {"results": [], "message": "no nodes to test"}

        results = speed_test(api, nodes)
        return {
            "results": [
                {"name": n.name, "delay": n.delay, "type": n.type}
                for n in results
            ]
        }
    except Exception as e:
        return {"error": str(e)}


# ── Request Handler ─────────────────────────────────────────────────────────

class WebHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass

    def _check_auth(self) -> bool:
        """Return True if request is authorized (or no secret is set)."""
        if not _WEB_SECRET:
            return True
        # Check Authorization header: "Bearer <secret>"
        auth = self.headers.get("Authorization", "")
        if auth == f"Bearer {_WEB_SECRET}":
            return True
        # Check query param: ?token=<secret>
        if f"token={_WEB_SECRET}" in self.path:
            return True
        return False

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            # Serve HTML without auth (login page handles token)
            self._serve_html()
        elif not self._check_auth():
            _err(self, "Unauthorized", 401)
        elif path == "/api/status":
            _json(self, api_status())
        elif path == "/api/nodes":
            _json(self, api_nodes())
        elif path == "/api/connections":
            _json(self, api_connections())
        elif path == "/api/subscriptions":
            _json(self, api_subscriptions())
        else:
            _err(self, "Not found", 404)

    def do_POST(self):
        if not self._check_auth():
            _err(self, "Unauthorized", 401)
            return
        path = self.path.split("?")[0]
        body = _read_body(self)
        handlers = {
            "/api/mode": lambda: api_set_mode(body),
            "/api/nodes/switch": lambda: api_switch_node(body),
            "/api/subscriptions": lambda: api_add_subscription(body),
            "/api/subscriptions/update": lambda: api_update_subscriptions(),
            "/api/restart": lambda: api_restart(),
            "/api/dns/flush": lambda: api_flush_dns(),
            "/api/fakeip/flush": lambda: api_flush_fakeip(),
            "/api/speed-test": lambda: api_speed_test(body),
        }
        fn = handlers.get(path)
        if fn:
            _json(self, fn())
        else:
            _err(self, "Not found", 404)

    def do_DELETE(self):
        if not self._check_auth():
            _err(self, "Unauthorized", 401)
            return
        path = self.path.split("?")[0]
        if path == "/api/connections":
            _json(self, api_close_all())
        elif path.startswith("/api/connections/"):
            conn_id = path[len("/api/connections/"):]
            _json(self, api_close_conn(conn_id))
        elif path.startswith("/api/subscriptions/"):
            try:
                idx = int(path[len("/api/subscriptions/"):])
                _json(self, api_remove_subscription(idx))
            except ValueError:
                _err(self, "invalid index")
        else:
            _err(self, "Not found", 404)

    def _serve_html(self):
        body = _get_html().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


# ── Server Runner ───────────────────────────────────────────────────────────

def run_server(host: str = WEB_HOST, port: int = WEB_PORT, secret: str = ""):
    global _WEB_SECRET
    if secret:
        _WEB_SECRET = secret
    elif not _WEB_SECRET:
        # Generate a random token if none provided
        import secrets as _secrets
        _WEB_SECRET = _secrets.token_urlsafe(16)

    server = ThreadingHTTPServer((host, port), WebHandler)
    print(f"\033[32m[QCG Web]\033[0m http://{host}:{port}")
    if _WEB_SECRET:
        print(f"\033[33m[QCG Web]\033[0m Token: {_WEB_SECRET}")
        print(f"\033[90mAccess: http://{host}:{port}?token={_WEB_SECRET}\033[0m")
    print(f"\033[90mPress Ctrl+C to stop\033[0m")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\033[33m[QCG Web]\033[0m Shutting down...")
        server.shutdown()
