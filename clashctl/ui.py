"""Terminal UI for clashctl — the qubes-clash-gateway controller.

Usage:
    clashctl /status              # Show status
    clashctl /mode global|rule|direct  # Switch mode
    clashctl /sub add <url>       # Add subscription
    clashctl /sub update          # Update all subscriptions
    clashctl /sub list            # List subscriptions
    clashctl /node <name>         # Select node
    clashctl /test [node]         # Speed test
    clashctl /help                # Show help
"""

import sys
from datetime import datetime

from .config import C_GREEN, C_RED, C_YELLOW, C_CYAN, C_DIM, C_BOLD, C_RESET
from .data import (
    load_config, load_preferences, save_preferences,
    load_subscriptions, save_subscriptions, time_ago,
)
from .api import ClashAPI, ClashAPIError
from .proxy import (
    detect_current_mode, apply_mode, apply_dns_preset,
    is_running, get_exit_ip, restart,
)
from .nodes import speed_test, get_proxy_groups, NodeInfo
from .parser import parse_subscription, parse_subscription_text
from .i18n import t


# ── Helpers ───────────────────────────────────────────────────────────────

def _print(s: str = ""):
    print(s)


def _ok(s: str):
    print(f"{C_GREEN}✓{C_RESET} {s}")


def _err(s: str):
    print(f"{C_RED}✗{C_RESET} {s}")


def _warn(s: str):
    print(f"{C_YELLOW}!{C_RESET} {s}")


def _info(s: str):
    print(f"{C_CYAN}→{C_RESET} {s}")


def _dim(s: str) -> str:
    return f"{C_DIM}{s}{C_RESET}"


def _green(s: str) -> str:
    return f"{C_GREEN}{s}{C_RESET}"


def _red(s: str) -> str:
    return f"{C_RED}{s}{C_RESET}"


def _yellow(s: str) -> str:
    return f"{C_YELLOW}{s}{C_RESET}"


def _mode_color(mode: str) -> str:
    if mode == "global":
        return _yellow("● GLOBAL")
    elif mode == "direct":
        return _dim("○ DIRECT")
    return _green("◐ RULE")


# ── Commands ──────────────────────────────────────────────────────────────

def cmd_status():
    """Show current status."""
    running = is_running()
    mode = detect_current_mode()
    prefs = load_preferences()

    _print()
    _print(f"  {C_BOLD}qubes-clash-gateway{C_RESET}")
    _print(f"  {'─' * 40}")

    # mihomo status
    if running:
        _print(f"  mihomo:     {_green('running')}")
        try:
            api = ClashAPI()
            ver = api.version()
            _print(f"  version:    {ver.get('version', '?')}")
        except Exception:
            pass
    else:
        _print(f"  mihomo:     {_red('stopped')}")
        _print()
        return

    # Mode
    _print(f"  mode:       {_mode_color(mode)}")

    # Exit IP
    exit_ip = get_exit_ip()
    if exit_ip:
        _print(f"  exit IP:    {exit_ip}")
    else:
        _print(f"  exit IP:    {_dim('unavailable')}")

    # DNS
    cfg = load_config()
    dns = cfg.get("dns", {})
    dns_mode = dns.get("enhanced-mode", "?")
    dns_port = dns.get("listen", "?")
    _print(f"  DNS:        {dns_mode} @ {dns_port}")

    # Nodes
    try:
        api = ClashAPI()
        groups = get_proxy_groups(api)
        total_nodes = sum(len(g.members) for g in groups if g.is_group)
        _print(f"  nodes:      {total_nodes}")
        for g in groups:
            if g.is_group and g.current:
                _print(f"  active:     {g.current} (in {g.name})")
    except Exception:
        pass

    # Subscriptions
    subs = load_subscriptions()
    sub_list = subs.get("subscriptions", [])
    if sub_list:
        _print(f"  subs:       {len(sub_list)}")
        for s in sub_list:
            _print(f"    {_dim('•')} {s.get('name', s.get('url', '?')[:40])}  {_dim(time_ago(s.get('last_update')))}")

    _print(f"  {'─' * 40}")
    _print()


def cmd_mode(args: list[str]):
    """Switch proxy mode: /mode global|rule|direct"""
    if not args:
        mode = detect_current_mode()
        _print(f"\n  Current mode: {_mode_color(mode)}\n  Usage: clashctl /mode global|rule|direct\n")
        return

    mode = args[0].lower()
    if mode not in ("global", "rule", "direct"):
        _err(f"Invalid mode: {mode}, options: global, rule, direct")
        return

    _info(f"Switching to {mode.upper()} mode...")
    if apply_mode(mode):
        _ok(f"Switched to {mode.upper()} mode")
    else:
        _err("Switch failed")


def cmd_sub(args: list[str]):
    """Subscription management: /sub add|update|list"""
    if not args:
        _print("\n  Usage:")
        _print("    clashctl /sub add <url>      Add subscription")
        _print("    clashctl /sub update         Update all subscriptions")
        _print("    clashctl /sub list           List subscriptions")
        _print("    clashctl /sub remove <name>  Remove subscription")
        _print()
        return

    action = args[0].lower()

    if action == "add":
        if len(args) < 2:
            _err("Please provide a subscription URL")
            return
        url = args[1]
        _info(f"Fetching subscription...")
        try:
            proxies = parse_subscription(url)
        except Exception as e:
            _err(f"Fetch failed: {e}")
            return

        if not proxies:
            _err("Subscription content is empty or parse failed")
            return

        name = f"sub-{datetime.now().strftime('%m%d%H%M')}"
        subs = load_subscriptions()
        sub_list = subs.get("subscriptions", [])
        sub_list.append({
            "name": name,
            "url": url,
            "proxy_count": len(proxies),
            "last_update": datetime.now().isoformat(),
        })
        subs["subscriptions"] = sub_list
        save_subscriptions(subs)

        # Merge proxies into config
        cfg = load_config()
        existing = cfg.get("proxies", [])
        existing_names = {p.get("name") for p in existing}
        added = 0
        for p in proxies:
            if p.get("name") not in existing_names:
                existing.append(p)
                existing_names.add(p.get("name"))
                added += 1
        cfg["proxies"] = existing
        from .data import save_config
        save_config(cfg)

        _ok(f"Added {len(proxies)} nodes ({added} new)")

    elif action == "update":
        subs = load_subscriptions()
        sub_list = subs.get("subscriptions", [])
        if not sub_list:
            _warn("No subscriptions")
            return

        cfg = load_config()
        all_new_proxies = []
        for sub in sub_list:
            url = sub.get("url", "")
            _info(f"Updating {sub.get('name', url[:30])}...")
            try:
                proxies = parse_subscription(url)
                all_new_proxies.extend(proxies)
                sub["proxy_count"] = len(proxies)
                sub["last_update"] = datetime.now().isoformat()
                _ok(f"  {len(proxies)} nodes")
            except Exception as e:
                _err(f"  Failed: {e}")

        if all_new_proxies:
            cfg["proxies"] = all_new_proxies
            from .data import save_config
            save_config(cfg)
            save_subscriptions(subs)

            # Update proxy groups
            from .proxy import apply_mode
            mode = detect_current_mode()
            apply_mode(mode)
            _ok(f"Total {len(all_new_proxies)} nodes updated")

    elif action == "list":
        subs = load_subscriptions()
        sub_list = subs.get("subscriptions", [])
        if not sub_list:
            _print("\n  No subscriptions\n")
            return
        _print()
        for s in sub_list:
            _print(f"  {_dim('•')} {s.get('name', '?')}  {s.get('proxy_count', 0)} nodes  {_dim(time_ago(s.get('last_update')))}")
            _print(f"    {C_DIM}{s.get('url', '?')[:60]}{C_RESET}")
        _print()

    elif action == "remove":
        if len(args) < 2:
            _err("Please provide subscription name")
            return
        name = args[1]
        subs = load_subscriptions()
        sub_list = subs.get("subscriptions", [])
        before = len(sub_list)
        sub_list = [s for s in sub_list if s.get("name") != name]
        if len(sub_list) == before:
            _err(f"Subscription not found: {name}")
            return
        subs["subscriptions"] = sub_list
        save_subscriptions(subs)
        _ok(f"Deleted subscription: {name}")


def cmd_node(args: list[str]):
    """Select node: /node <name>"""
    if not args:
        # List available nodes
        try:
            api = ClashAPI()
            groups = get_proxy_groups(api)
            _print()
            for g in groups:
                if g.is_group:
                    _print(f"  {C_BOLD}{g.name}{C_RESET} ({g.group_type})")
                    if g.current:
                        _print(f"    Current: {_green(g.current)}")
                    for m in g.members:
                        marker = " →" if m == g.current else "  "
                        _print(f"    {marker} {m}")
                    _print()
        except Exception as e:
            _err(f"Failed to get nodes: {e}")
        return

    node_name = " ".join(args)
    try:
        api = ClashAPI()
        # Find which group this node belongs to
        groups = get_proxy_groups(api)
        found = False
        for g in groups:
            if g.is_group and node_name in g.members:
                api.switch_proxy(g.name, node_name)
                _ok(f"Switched to {node_name} (group: {g.name})")
                found = True
                break

        if not found:
            # Try direct switch on GLOBAL group
            try:
                api.switch_proxy("GLOBAL", node_name)
                _ok(f"Switched to {node_name}")
            except Exception:
                _err(f"Node not found: {node_name}")
                _info("Use clashctl /node to view available nodes")
    except Exception as e:
        _err(f"Switch failed: {e}")


def cmd_test(args: list[str]):
    """Speed test: /test [node_name]"""
    _info("Testing speed...")
    try:
        api = ClashAPI()
        cfg = load_config()
        all_names = [p.get("name", "") for p in cfg.get("proxies", []) if p.get("name")]

        if args:
            node_name = " ".join(args)
            if node_name not in all_names:
                _err(f"Node not found: {node_name}")
                return
            test_names = [node_name]
        else:
            if not all_names:
                _warn("No nodes to test")
                return
            test_names = all_names

        # Build NodeInfo objects for speed_test()
        from .nodes import NodeInfo
        node_infos = [NodeInfo(name=n, type="") for n in test_names]
        speed_test(api, node_infos)

        _print()
        for node in node_infos:
            if node.delay > 0:
                _print(f"  {_green('●')} {node.name}: {node.delay}ms")
            elif node.delay == 0:
                _print(f"  {_red('○')} {node.name}: {_dim('timeout')}")
            else:
                _print(f"  {_dim('○')} {node.name}: {_dim('untested')}")
        _print()
    except Exception as e:
        _err(f"Speed test failed: {e}")


def cmd_restart():
    """Restart mihomo."""
    _info("Restarting mihomo...")
    if restart():
        _ok("Restarted")
    else:
        _err("Restart failed")

def cmd_web(args: list[str]):
    """Start web UI."""
    port = 9091
    secret = ""
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--secret" and i + 1 < len(args):
            secret = args[i + 1]
            i += 2
        elif arg == "--no-auth":
            secret = ""
            i += 1
        else:
            try:
                port = int(arg)
            except ValueError:
                _err(f"Invalid port: {arg}")
                return
            i += 1
    from .web import run_server
    run_server("127.0.0.1", port, secret)



def cmd_help():
    """Show help."""
    _print()
    _print(f"  {C_BOLD}clashctl{C_RESET} — qubes-clash-gateway controller")
    _print(f"  {'─' * 40}")
    _print(f"  /status              Show status")
    _print(f"  /mode global|rule|direct  Switch mode")
    _print(f"  /sub add <url>       Add subscription")
    _print(f"  /sub update          Update all subscriptions")
    _print(f"  /sub list            List subscriptions")
    _print(f"  /sub remove <name>   Remove subscription")
    _print(f"  /node                List all nodes")
    _print(f"  /node <name>         Select node")
    _print(f"  /test [node]         Speed test")
    _print(f"  /dns fake-ip|redir-host  Switch DNS mode")
    _print(f"  /restart             Restart mihomo")
    _print(f"  /help                Show help")
    _print(f"  /web [port]          Start Web UI (default 9091)")
    _print(f"  {'─' * 40}")
    _print(f"  {C_DIM}alias: /s=/status /m=/mode /n=/node /t=/test{C_RESET}")
    _print()


# ── Alias mapping ─────────────────────────────────────────────────────────

ALIASES = {
    "/s": "/status",
    "/m": "/mode",
    "/n": "/node",
    "/t": "/test",
    "/h": "/help",
    "/r": "/restart",
    "/w": "/web",
}


# ── Main entry point ──────────────────────────────────────────────────────

def main():
    """CLI entry point."""
    args = sys.argv[1:]

    if not args:
        cmd_help()
        return

    cmd = args[0].lower()

    # Resolve aliases
    if cmd in ALIASES:
        cmd = ALIASES[cmd]

    # Route to handler
    if cmd in ("/status", "status"):
        cmd_status()
    elif cmd in ("/mode", "mode"):
        cmd_mode(args[1:])
    elif cmd in ("/sub", "sub"):
        cmd_sub(args[1:])
    elif cmd in ("/node", "node"):
        cmd_node(args[1:])
    elif cmd in ("/test", "test"):
        cmd_test(args[1:])
    elif cmd in ("/dns", "dns"):
        if len(args) < 2:
            _print(f"\n  Usage: clashctl /dns fake-ip|redir-host\n")
        else:
            if apply_dns_preset(args[1]):
                _ok(f"DNS switched to {args[1]}")
            else:
                _err(f"Invalid DNS mode: {args[1]}")
    elif cmd in ("/restart", "restart"):
        cmd_restart()
    elif cmd in ("/web", "web"):
        cmd_web(args[1:])
    elif cmd in ("/help", "help", "--help", "-h"):
        cmd_help()
    else:
        _err(f"Unknown command: {cmd}")
        _info("Use clashctl /help to view help")
