"""Node parsing, speed test, and IP geolocation for mihomo (Clash Meta).

Provides:
  - parse_nodes()          — extract proxy nodes from mihomo API
  - get_proxy_groups()     — list proxy groups with their members
  - speed_test()           — concurrent latency test for a list of nodes
  - get_exit_ip()          — query the exit IP through the proxy
  - geolocate_ip()         — get GeoIP info for an IP address
  - format_delay()         — colourised delay string
  - NodeInfo dataclass     — structured proxy node info
"""

import json
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Optional

from .config import SPEEDTEST_TIMEOUT, SPEEDTEST_WORKERS, C_GREEN, C_RED, C_GRAY, C_RESET, C_DIM
from .i18n import t

# Try to import get_region_name; fall back to a passthrough if not available
try:
    from .i18n import get_region_name
except ImportError:
    def get_region_name(code: str) -> str:
        return code


# ── Data structures ────────────────────────────────────────────────────

@dataclass
class NodeInfo:
    """Represents a single proxy node."""
    name: str
    type: str                         # ss, vmess, vless, trojan, hysteria2, ...
    server: str = ""
    port: int = 0
    delay: int = -1                   # -1 = untested, 0 = timeout/error
    group: str = ""                   # which proxy group it belongs to
    is_group: bool = False            # True if this is a proxy-group entry
    group_type: str = ""              # urltest, fallback, select, ...
    current: str = ""                 # currently selected member (for groups)
    members: list = field(default_factory=list)  # member names (for groups)
    extra: dict = field(default_factory=dict)    # raw proxy config dict

    @property
    def reachable(self) -> bool:
        return self.delay > 0

    @property
    def delay_str(self) -> str:
        return format_delay(self.delay)


# ── Node parsing ───────────────────────────────────────────────────────

# Built-in virtual proxies that are not real nodes
_VIRTUAL_NAMES = frozenset({"DIRECT", "REJECT", "GLOBAL", "PASS"})
_GROUP_TYPES = frozenset({"Selector", "URLTest", "Fallback", "LoadBalance",
                          "Relay", "Compatible", "Fallback-UD"})


def parse_nodes(api) -> list[NodeInfo]:
    """Fetch all proxies from the mihomo API and return a list of NodeInfo.

    Args:
        api: A ClashAPI instance.

    Returns:
        Flat list of NodeInfo objects — real proxy nodes only (no DIRECT/REJECT).
    """
    data = api.get_proxies()
    raw = data.get("proxies", {})
    nodes: list[NodeInfo] = []

    for name, info in raw.items():
        ptype = info.get("type", "unknown")
        now = info.get("now", "")
        all_members = info.get("all", [])

        if ptype in _GROUP_TYPES:
            # This is a proxy group — store it and expand its members
            node = NodeInfo(
                name=name,
                type=ptype,
                is_group=True,
                group_type=ptype,
                current=now,
                members=[m for m in all_members if m not in _VIRTUAL_NAMES],
                extra=info,
            )
            nodes.append(node)
        elif name not in _VIRTUAL_NAMES:
            # Real proxy node
            node = NodeInfo(
                name=name,
                type=ptype,
                server=info.get("server", ""),
                port=info.get("port", 0),
                extra=info,
            )
            nodes.append(node)

    return nodes


def get_group_nodes(api, group_name: str) -> list[NodeInfo]:
    """Get the member nodes of a specific proxy group.

    Args:
        api: A ClashAPI instance.
        group_name: The proxy group name (e.g. "Proxy", "auto").

    Returns:
        List of NodeInfo for member nodes (excluding virtual proxies).
    """
    data = api.get_proxies()
    raw = data.get("proxies", {})

    group_info = raw.get(group_name, {})
    all_members = group_info.get("all", [])

    nodes: list[NodeInfo] = []
    for member_name in all_members:
        if member_name in _VIRTUAL_NAMES:
            continue
        member_info = raw.get(member_name, {})
        ptype = member_info.get("type", "unknown")
        node = NodeInfo(
            name=member_name,
            type=ptype,
            server=member_info.get("server", ""),
            port=member_info.get("port", 0),
            group=group_name,
            extra=member_info,
        )
        nodes.append(node)

    return nodes


def get_proxy_groups(api) -> list[NodeInfo]:
    """List all proxy groups (Selector, URLTest, Fallback, etc.).

    Args:
        api: A ClashAPI instance.

    Returns:
        List of NodeInfo where is_group=True.
    """
    data = api.get_proxies()
    raw = data.get("proxies", {})
    groups: list[NodeInfo] = []

    for name, info in raw.items():
        ptype = info.get("type", "unknown")
        if ptype in _GROUP_TYPES:
            all_members = info.get("all", [])
            groups.append(NodeInfo(
                name=name,
                type=ptype,
                is_group=True,
                group_type=ptype,
                current=info.get("now", ""),
                members=[m for m in all_members if m not in _VIRTUAL_NAMES],
                extra=info,
            ))

    return groups


def switch_node(api, group: str, node_name: str) -> None:
    """Switch the selected proxy in a group.

    Args:
        api: A ClashAPI instance.
        group: The proxy group name.
        node_name: The node to select.
    """
    api.switch_proxy(group, node_name)


# ── Speed test ─────────────────────────────────────────────────────────

def _test_single(api, name: str, url: str, timeout: int) -> tuple[str, int]:
    """Test latency for one proxy node. Returns (name, delay_ms)."""
    try:
        result = api.proxy_delay(name, url=url, timeout=timeout * 1000)
        return (name, result.get("delay", 0))
    except Exception:
        return (name, 0)


def speed_test(
    api,
    nodes: list[NodeInfo],
    url: str = "https://www.gstatic.com/generate_204",
    timeout: int = SPEEDTEST_TIMEOUT,
    workers: int = SPEEDTEST_WORKERS,
    progress_callback=None,
) -> list[NodeInfo]:
    """Run concurrent latency tests on a list of nodes.

    Args:
        api: ClashAPI instance.
        nodes: List of NodeInfo to test. Results are written in-place to .delay.
        url: Test URL (default Google generate_204).
        timeout: Per-node timeout in seconds.
        workers: Max concurrent workers.
        progress_callback: Optional callable(done, total) called after each node.

    Returns:
        The same list with .delay populated.
    """
    # Build a mapping from node name → NodeInfo for quick lookup
    name_map: dict[str, NodeInfo] = {}
    test_names: list[str] = []
    for node in nodes:
        if node.is_group:
            continue
        name_map[node.name] = node
        test_names.append(node.name)

    if not test_names:
        return nodes

    total = len(test_names)
    done = 0

    with ThreadPoolExecutor(max_workers=min(workers, total)) as pool:
        futures = {
            pool.submit(_test_single, api, name, url, timeout): name
            for name in test_names
        }
        for future in as_completed(futures):
            name, delay = future.result()
            if name in name_map:
                name_map[name].delay = delay
            done += 1
            if progress_callback:
                progress_callback(done, total)

    # Sort: reachable (fastest first), then unreachable
    nodes.sort(key=lambda n: (0 if n.delay > 0 else 1, n.delay))

    return nodes


# ── Delay formatting ───────────────────────────────────────────────────

def format_delay(delay: int) -> str:
    """Return a colourised delay string.

    - delay < 0  → "—" (untested)
    - delay == 0 → "timeout" (red)
    - delay < 200 → green
    - delay < 500 → default
    - else → red
    """
    if delay < 0:
        return f"{C_DIM}—{C_RESET}"
    if delay == 0:
        return f"{C_RED}{t('node_timeout')}{C_RESET}"
    if delay < 200:
        return f"{C_GREEN}{delay}ms{C_RESET}"
    if delay < 500:
        return f"{delay}ms"
    return f"{C_RED}{delay}ms{C_RESET}"


# ── IP Geolocation ─────────────────────────────────────────────────────

# Multiple fallback GeoIP services (free, no key needed)
_GEOIP_URLS = [
    "https://ipinfo.io/json",
    "http://ip-api.com/json/?fields=status,message,country,countryCode,region,city,isp,org,query",
    "https://ipapi.co/json/",
]

_EXIT_IP_URLS = [
    "https://api.ipify.org?format=json",
    "https://ifconfig.me/ip",
    "https://ipinfo.io/ip",
]


def _get_mihomo_proxy_handler(api=None):
    """Build a urllib ProxyHandler that routes through mihomo mixed-port."""
    if api is None:
        return urllib.request.ProxyHandler({})  # no proxy
    try:
        cfg = api.get_configs()
        port = cfg.get("mixed-port", 7890)
    except Exception:
        port = 7890
    proxy_url = f"http://127.0.0.1:{port}"
    return urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})


def get_exit_ip(api=None, timeout: int = 10) -> str:
    """Query the exit IP address through the mihomo proxy.

    Args:
        api: Optional ClashAPI instance for proxy routing.
             When provided, requests go through mihomo mixed-port.
        timeout: Request timeout in seconds.

    Returns:
        The exit IP as a string, or "Unknown" on failure.
    """
    opener = urllib.request.build_opener(_get_mihomo_proxy_handler(api))
    for url in _EXIT_IP_URLS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "clashctl/1.0"})
            with opener.open(req, timeout=timeout) as resp:
                body = resp.read().decode().strip()
                # ipify returns JSON, the others return plain text
                if body.startswith("{"):
                    return json.loads(body).get("ip", body)
                return body
        except Exception:
            continue
    return "Unknown"


def geolocate_ip(ip: str = "", timeout: int = 10) -> dict:
    """Get GeoIP information for an IP address.

    Args:
        ip: IP to look up (empty = use caller's IP).
        timeout: Request timeout in seconds.

    Returns:
        Dict with keys: ip, country, country_code, region, city, isp, org.
        All values default to "Unknown" on failure.
    """
    result = {
        "ip": ip or "Unknown",
        "country": "Unknown",
        "country_code": "",
        "region": "Unknown",
        "city": "Unknown",
        "isp": "Unknown",
        "org": "Unknown",
    }

    # Try ipinfo.io first
    try:
        url = f"https://ipinfo.io/{ip}/json" if ip else "https://ipinfo.io/json"
        req = urllib.request.Request(url, headers={"User-Agent": "clashctl/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            result["ip"] = data.get("ip", ip or "Unknown")
            result["country"] = get_region_name(data.get("country", ""))
            result["country_code"] = data.get("country", "")
            result["region"] = data.get("region", "Unknown")
            result["city"] = data.get("city", "Unknown")
            org = data.get("org", "Unknown")
            result["isp"] = org
            result["org"] = org
            return result
    except Exception:
        pass

    # Fallback: ip-api.com
    try:
        url = f"http://ip-api.com/json/{ip}" if ip else "http://ip-api.com/json/"
        req = urllib.request.Request(url, headers={"User-Agent": "clashctl/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            if data.get("status") == "success":
                result["ip"] = data.get("query", ip or "Unknown")
                result["country"] = data.get("country", "Unknown")
                result["country_code"] = data.get("countryCode", "")
                result["region"] = data.get("region", "Unknown")
                result["city"] = data.get("city", "Unknown")
                result["isp"] = data.get("isp", "Unknown")
                result["org"] = data.get("org", "Unknown")
                return result
    except Exception:
        pass

    # Fallback: ipapi.co
    try:
        url = f"https://ipapi.co/{ip}/json/" if ip else "https://ipapi.co/json/"
        req = urllib.request.Request(url, headers={"User-Agent": "clashctl/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            result["ip"] = data.get("ip", ip or "Unknown")
            result["country"] = data.get("country_name", "Unknown")
            result["country_code"] = data.get("country_code", "")
            result["region"] = data.get("region", "Unknown")
            result["city"] = data.get("city", "Unknown")
            result["isp"] = data.get("org", "Unknown")
            result["org"] = data.get("org", "Unknown")
            return result
    except Exception:
        pass

    return result


def get_exit_geo(api=None, timeout: int = 10) -> dict:
    """Get the geolocation of the current exit IP.

    Convenience function combining get_exit_ip() + geolocate_ip().

    Args:
        api: Optional ClashAPI for proxy routing.
        timeout: Request timeout.

    Returns:
        GeoIP dict (same format as geolocate_ip).
    """
    ip = get_exit_ip(api, timeout)
    if ip == "Unknown":
        return {
            "ip": "Unknown",
            "country": "Unknown",
            "country_code": "",
            "region": "Unknown",
            "city": "Unknown",
            "isp": "Unknown",
            "org": "Unknown",
        }
    return geolocate_ip(ip, timeout)


# ── Convenience formatting ─────────────────────────────────────────────

def node_display_name(node: NodeInfo) -> str:
    """Return a display-friendly name for a node, including type tag."""
    tag = f"{C_DIM}[{node.type}]{C_RESET}" if not node.is_group else f"{C_DIM}[{node.group_type}]{C_RESET}"
    return f"{tag} {node.name}"


def node_summary(node: NodeInfo) -> str:
    """One-line summary of a node for TUI display."""
    parts = [node.name]
    parts.append(f"{C_DIM}({node.type}){C_RESET}")
    if node.server:
        parts.append(f"{C_GRAY}{node.server}:{node.port}{C_RESET}")
    if node.delay >= 0:
        parts.append(format_delay(node.delay))
    return " ".join(parts)


def group_summary(group: NodeInfo) -> str:
    """One-line summary of a proxy group."""
    parts = [group.name]
    parts.append(f"{C_DIM}[{group.group_type}]{C_RESET}")
    if group.current:
        parts.append(f"→ {group.current}")
    parts.append(f"{C_DIM}({len(group.members)} nodes){C_RESET}")
    return " ".join(parts)


def geo_summary(geo: dict) -> str:
    """Format GeoIP dict into a readable one-liner."""
    parts = []
    ip = geo.get("ip", "Unknown")
    country = geo.get("country", "")
    city = geo.get("city", "")
    isp = geo.get("isp", "")

    parts.append(f"{ip}")
    location = ", ".join(filter(None, [city, country]))
    if location:
        parts.append(f"({location})")
    if isp and isp != "Unknown":
        parts.append(f"{C_DIM}{isp}{C_RESET}")

    return " ".join(parts)
