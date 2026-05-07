"""Health monitoring daemon for mihomo proxy nodes on Qubes OS.

Polls the mihomo ClashAPI for proxy status/latency, logs unhealthy nodes
to syslog, and auto-restarts mihomo if the API is unreachable for too long.

Since mihomo's urltest proxy-groups handle automatic node switching, this
monitor is primarily for logging/alerting rather than config manipulation.

Usage:
    python -m clashctl.monitor          # run in foreground
    python -m clashctl.monitor &        # run as background daemon
    kill $(cat /tmp/clash-monitor.pid)  # stop
"""

import os
import signal
import sys
import time
import syslog
from typing import Optional

from .config import SPEEDTEST_TIMEOUT
from .api import ClashAPI, ClashAPIError
from .data import load_config, load_preferences

# ── Constants ────────────────────────────────────────────────────────────────

CHECK_INTERVAL = 300        # seconds between health check cycles
NODE_TIMEOUT = 3            # seconds timeout per node delay check
MAX_FAIL_COUNT = 3          # consecutive failures before warning
MONITOR_LOG_TAG = "clash-monitor"

PID_FILE = "/tmp/clash-monitor.pid"
MIHOMO_RESTART_CMD = "systemctl restart mihomo"
API_UNREACHABLE_THRESHOLD = 3  # consecutive API failures before restart

# ── Global state ─────────────────────────────────────────────────────────────

_running = True
_api_fail_count = 0         # consecutive API connection failures
_node_failures: dict[str, int] = {}  # node_name -> consecutive failure count


# ── Logging ──────────────────────────────────────────────────────────────────

def log(msg: str) -> None:
    """Write a message to syslog and stderr."""
    syslog.syslog(syslog.LOG_WARNING, msg)
    print(f"[{MONITOR_LOG_TAG}] {msg}", file=sys.stderr, flush=True)


# ── Signal handling ──────────────────────────────────────────────────────────

def signal_handler(sig: int, frame) -> None:
    """Handle SIGTERM/SIGINT for graceful shutdown."""
    global _running
    log(f"Received signal {sig}, shutting down…")
    _running = False


# ── PID file management ─────────────────────────────────────────────────────

def write_pid() -> None:
    """Write current PID to the PID file."""
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))


def cleanup_pid() -> None:
    """Remove the PID file on exit."""
    try:
        os.unlink(PID_FILE)
    except FileNotFoundError:
        pass


# ── Proxy node operations ───────────────────────────────────────────────────

def get_proxy_nodes(api: ClashAPI) -> list[str]:
    """Get all individual proxy node names from the API.

    Filters out proxy groups, DIRECT, REJECT, and GLOBAL.
    Returns a list of node name strings.
    """
    try:
        proxies_data = api.get_proxies()
    except ClashAPIError as exc:
        log(f"Failed to fetch proxies: {exc}")
        return []

    proxies = proxies_data.get("proxies", {})
    nodes: list[str] = []

    for name, info in proxies.items():
        # Skip proxy groups (they have 'type' like 'Selector', 'URLTest', etc.)
        proxy_type = info.get("type", "")
        if proxy_type in ("Selector", "URLTest", "Fallback", "LoadBalance",
                          "Relay", "Compatible", "Pass"):
            continue
        # Skip built-in proxies
        if name in ("DIRECT", "REJECT", "GLOBAL"):
            continue
        nodes.append(name)

    return nodes


def check_all_nodes(api: ClashAPI, nodes: list[str]) -> dict[str, Optional[int]]:
    """Check latency for all nodes via the API delay endpoint.

    Returns a dict mapping node name to delay (ms), or None/0 on failure.
    """
    results: dict[str, Optional[int]] = {}
    timeout_ms = NODE_TIMEOUT * 1000

    for node in nodes:
        try:
            resp = api.proxy_delay(
                name=node,
                url="https://www.gstatic.com/generate_204",
                timeout=timeout_ms,
            )
            delay = resp.get("delay", 0)
            results[node] = delay
        except ClashAPIError:
            results[node] = None
        except Exception as exc:
            log(f"Unexpected error checking {node}: {exc}")
            results[node] = None

    return results


# ── Main check cycle ────────────────────────────────────────────────────────

def run_check() -> bool:
    """Run a single health check cycle.

    Returns True if the check completed successfully, False if the API
    was unreachable.
    """
    global _api_fail_count, _node_failures

    api = ClashAPI()

    # ── Step 1: Verify API is reachable ──────────────────────────────────
    try:
        version_info = api.version()
        _api_fail_count = 0  # reset on success
    except ClashAPIError as exc:
        _api_fail_count += 1
        log(f"mihomo API unreachable (attempt {_api_fail_count}): {exc}")

        if _api_fail_count >= API_UNREACHABLE_THRESHOLD:
            log(
                f"API unreachable for {_api_fail_count} consecutive checks, "
                f"attempting mihomo restart…"
            )
            ret = os.system(MIHOMO_RESTART_CMD)
            if ret == 0:
                log("mihomo restart command issued successfully")
                _api_fail_count = 0
            else:
                log(f"mihomo restart command failed (exit code {ret})")
        return False

    # ── Step 2: Get proxy nodes ──────────────────────────────────────────
    nodes = get_proxy_nodes(api)
    if not nodes:
        log("No proxy nodes found (API returned empty list)")
        return True

    # ── Step 3: Check node latency ───────────────────────────────────────
    results = check_all_nodes(api, nodes)

    healthy = 0
    unhealthy = 0
    for node, delay in results.items():
        if delay is not None and delay > 0:
            # Node is healthy
            if node in _node_failures and _node_failures[node] > 0:
                log(f"Node recovered: {node} (delay={delay}ms)")
                _node_failures[node] = 0
            healthy += 1
        else:
            # Node failed
            _node_failures[node] = _node_failures.get(node, 0) + 1
            unhealthy += 1
            if _node_failures[node] >= MAX_FAIL_COUNT:
                log(
                    f"Node unhealthy ({_node_failures[node]} consecutive failures): {node}"
                )

    # ── Step 4: Summary ──────────────────────────────────────────────────
    log(
        f"Health check: {healthy} healthy, {unhealthy} unhealthy "
        f"out of {len(nodes)} nodes"
    )

    return True


# ── Daemon entry point ──────────────────────────────────────────────────────

def main() -> None:
    """Main daemon loop."""
    global _running

    # Initialize syslog
    syslog.openlog(MONITOR_LOG_TAG, syslog.LOG_PID, syslog.LOG_DAEMON)

    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Write PID file
    write_pid()
    log(f"clash-monitor started (PID={os.getpid()}, interval={CHECK_INTERVAL}s)")

    try:
        while _running:
            try:
                run_check()
            except Exception as exc:
                log(f"Unhandled exception in check cycle: {exc}")

            # Sleep in small increments so we respond to signals promptly
            deadline = time.time() + CHECK_INTERVAL
            while _running and time.time() < deadline:
                time.sleep(min(1.0, deadline - time.time()))
    finally:
        cleanup_pid()
        log("clash-monitor stopped")
        syslog.closelog()


if __name__ == "__main__":
    main()
