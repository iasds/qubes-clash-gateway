"""mihomo RESTful API wrapper

Thin synchronous client for the mihomo (Clash Meta) external-controller HTTP API.
All public methods return parsed JSON (dict/list) on success or raise
ClashAPIError on non-2xx responses.

Uses urllib.request — no third-party HTTP library required.
"""
import json
import urllib.request
import urllib.error
import urllib.parse
from typing import Any, Optional

from .config import API_BASE, API_PORT, API_SECRET


class ClashAPIError(Exception):
    """Raised when the mihomo API returns a non-2xx status."""

    def __init__(self, status: int, message: str = ""):
        self.status = status
        self.message = message
        super().__init__(f"HTTP {status}: {message}")


class ClashAPI:
    """Low-level wrapper around the mihomo external-controller REST API.

    Usage::

        api = ClashAPI()                        # default 127.0.0.1:9090
        api = ClashAPI(host="192.168.1.1")      # custom host
        info = api.version()
        api.mode("rule")
    """

    def __init__(
        self,
        host: str = API_BASE,
        port: int = API_PORT,
        secret: Optional[str] = API_SECRET,
    ):
        self.base_url = f"{host}:{port}"
        self.secret = secret

    # ── internal helpers ──────────────────────────────────────────

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict] = None,
        body: Optional[dict] = None,
        timeout: int = 10,
    ) -> Any:
        """Send an HTTP request and return parsed JSON (or None for 204)."""
        url = f"{self.base_url}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.secret:
            headers["Authorization"] = f"Bearer {self.secret}"

        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 204:
                    return None
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            msg = ""
            try:
                msg = exc.read().decode()
            except Exception:
                pass
            raise ClashAPIError(exc.code, msg) from exc
        except urllib.error.URLError as exc:
            raise ClashAPIError(0, f"Connection failed: {exc.reason}") from exc

    def _get(self, path: str, **kw: Any) -> Any:
        return self._request("GET", path, **kw)

    def _put(self, path: str, **kw: Any) -> Any:
        return self._request("PUT", path, **kw)

    def _patch(self, path: str, **kw: Any) -> Any:
        return self._request("PATCH", path, **kw)

    def _post(self, path: str, **kw: Any) -> Any:
        return self._request("POST", path, **kw)

    def _delete(self, path: str, **kw: Any) -> Any:
        return self._request("DELETE", path, **kw)

    # ── Version ───────────────────────────────────────────────────

    def version(self) -> dict:
        """Return mihomo version info.  e.g. {"version": "v1.19.0"}"""
        return self._get("/version")

    # ── Configs ───────────────────────────────────────────────────

    def get_configs(self) -> dict:
        """Get the current active configuration."""
        return self._get("/configs")

    def patch_configs(self, **kwargs: Any) -> None:
        """Partial-update the running configuration.

        Common keyword arguments:
            mode: str           – "rule", "global", or "direct"
            log_level: str      – "silent", "error", "warning", "info", "debug"
            mixed_port: int     – mixed HTTP/SOCKS5 port
            allow_lan: bool     – allow LAN connections
            bind_address: str   – bind address
        """
        # Convert snake_case to camelCase-ish keys mihomo expects
        mapping = {
            "log_level": "log-level",
            "mixed_port": "mixed-port",
            "allow_lan": "allow-lan",
            "bind_address": "bind-address",
            "socks_port": "socks-port",
            "port": "port",
            "ipv6": "ipv6",
            "tcp_concurrent": "tcp-concurrent",
            "find_process_mode": "find-process-mode",
            "global_client_fingerprint": "global-client-fingerprint",
        }
        body: dict[str, Any] = {}
        for key, val in kwargs.items():
            body[mapping.get(key, key)] = val
        self._patch("/configs", body=body)

    def put_configs(self, path: str, force: bool = False) -> None:
        """Reload configuration from a file path on disk.

        Args:
            path: Absolute path to the YAML config file.
            force: If True, force reload even if unchanged.
        """
        self._put("/configs", params={"path": path, "force": str(force).lower()})

    # ── Mode shortcuts ────────────────────────────────────────────

    def mode(self, value: str) -> None:
        """Set proxy mode: 'rule', 'global', or 'direct'."""
        self.patch_configs(mode=value)

    def get_mode(self) -> str:
        """Return current proxy mode."""
        cfg = self.get_configs()
        return cfg.get("mode", "rule")

    # ── Proxies ───────────────────────────────────────────────────

    def get_proxies(self) -> dict:
        """Return all proxies and proxy groups.

        The result dict has keys like "proxies" (underlying nodes) and group
        names mapped to their config + members.
        """
        return self._get("/proxies")

    def get_proxy(self, name: str) -> dict:
        """Get details for a single proxy or group."""
        return self._get(f"/proxies/{urllib.parse.quote(name, safe='')}")

    def switch_proxy(self, group: str, name: str) -> None:
        """Select a proxy node within a proxy group.

        Args:
            group: The proxy group name (e.g. "auto", "Proxy").
            name:  The proxy node name to select.
        """
        self._put(
            f"/proxies/{urllib.parse.quote(group, safe='')}",
            body={"name": name},
        )

    def proxy_delay(
        self,
        name: str,
        url: str = "https://www.gstatic.com/generate_204",
        timeout: int = 5000,
    ) -> dict:
        """Test latency for a single proxy.

        Args:
            name:    Proxy node name.
            url:     Test URL (default Google generate_204).
            timeout: Timeout in milliseconds.

        Returns:
            {"delay": <ms>} on success.
        """
        return self._get(
            f"/proxies/{urllib.parse.quote(name, safe='')}/delay",
            params={"url": url, "timeout": timeout},
            timeout=max(timeout // 1000 + 5, 15),
        )

    def group_delay(
        self,
        group: str,
        url: str = "https://www.gstatic.com/generate_204",
        timeout: int = 5000,
    ) -> dict:
        """Test latency for all proxies in a group (url-test).

        Returns a dict mapping node names to delay results.
        """
        # mihomo supports group-level delay test via PUT with empty body
        result: dict[str, Any] = {}
        proxies_info = self.get_proxy(group)
        members = proxies_info.get("all", proxies_info.get("now", []))
        # 'all' is the list of member names; 'now' is the currently selected
        if isinstance(members, list):
            for member in members:
                if member in ("DIRECT", "REJECT", "GLOBAL"):
                    continue
                try:
                    result[member] = self.proxy_delay(member, url, timeout)
                except ClashAPIError:
                    result[member] = {"delay": 0, "error": True}
        return result

    # ── Proxy Providers ───────────────────────────────────────────

    def get_proxy_providers(self) -> dict:
        """List all proxy providers."""
        return self._get("/providers/proxies")

    def get_proxy_provider(self, name: str) -> dict:
        """Get a specific proxy provider and its proxies."""
        return self._get(f"/providers/proxies/{urllib.parse.quote(name, safe='')}")

    def update_proxy_provider(self, name: str) -> None:
        """Force-update a proxy provider (re-download)."""
        self._put(f"/providers/proxies/{urllib.parse.quote(name, safe='')}")

    def healthcheck_proxy_provider(self, name: str) -> None:
        """Trigger healthcheck for all proxies in a provider."""
        self._get(
            f"/providers/proxies/{urllib.parse.quote(name, safe='')}/healthcheck"
        )

    # ── Rule Providers ────────────────────────────────────────────

    def get_rule_providers(self) -> dict:
        """List all rule providers."""
        return self._get("/providers/rules")

    def get_rule_provider(self, name: str) -> dict:
        """Get a specific rule provider."""
        return self._get(f"/providers/rules/{urllib.parse.quote(name, safe='')}")

    def update_rule_provider(self, name: str) -> None:
        """Force-update a rule provider (re-download)."""
        self._put(f"/providers/rules/{urllib.parse.quote(name, safe='')}")

    # ── Rules ─────────────────────────────────────────────────────

    def get_rules(self) -> list:
        """Return the active rule list."""
        data = self._get("/rules")
        return data.get("rules", [])

    # ── Connections ───────────────────────────────────────────────

    def get_connections(self) -> dict:
        """Return all active connections."""
        return self._get("/connections")

    def close_connection(self, connection_id: str) -> None:
        """Close a specific connection by its ID."""
        self._delete(f"/connections/{urllib.parse.quote(connection_id, safe='')}")

    def close_all_connections(self) -> None:
        """Close all active connections."""
        self._delete("/connections")

    # ── DNS ───────────────────────────────────────────────────────

    def flush_dns_cache(self) -> None:
        """Flush the DNS cache."""
        self._post("/cache/dns/flush")

    def flush_fake_ip_cache(self) -> None:
        """Flush the fake-IP mapping cache."""
        self._post("/cache/fakeip/flush")

    # ── Subscriptions / Providers update ──────────────────────────

    def update_geoip(self) -> None:
        """Trigger GeoIP database update."""
        self._post("/configs/geoip")

    def update_geodata(self) -> None:
        """Trigger GeoData database update."""
        self._post("/configs/geodata")

    # ── Convenience: reload config from disk ──────────────────────

    def reload(self, config_path: str = "/rw/config/clash/config.yaml") -> None:
        """Reload mihomo configuration from the given file path."""
        self.put_configs(config_path, force=True)
