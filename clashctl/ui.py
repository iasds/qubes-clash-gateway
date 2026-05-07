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
        groups = get_proxy_groups()
        total_nodes = 0
        for g in groups:
            if not g.is_group:
                total_nodes += 1
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
        _print(f"\n  当前模式: {_mode_color(mode)}\n  用法: clashctl /mode global|rule|direct\n")
        return

    mode = args[0].lower()
    if mode not in ("global", "rule", "direct"):
        _err(f"无效模式: {mode}，可选: global, rule, direct")
        return

    _info(f"切换到 {mode.upper()} 模式...")
    if apply_mode(mode):
        _ok(f"已切换到 {mode.upper()} 模式")
    else:
        _err("切换失败")


def cmd_sub(args: list[str]):
    """Subscription management: /sub add|update|list"""
    if not args:
        _print("\n  用法:")
        _print("    clashctl /sub add <url>      添加订阅")
        _print("    clashctl /sub update         更新所有订阅")
        _print("    clashctl /sub list           列出订阅")
        _print("    clashctl /sub remove <name>  删除订阅")
        _print()
        return

    action = args[0].lower()

    if action == "add":
        if len(args) < 2:
            _err("请提供订阅 URL")
            return
        url = args[1]
        _info(f"获取订阅...")
        try:
            proxies = parse_subscription(url)
        except Exception as e:
            _err(f"获取失败: {e}")
            return

        if not proxies:
            _err("订阅内容为空或解析失败")
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

        _ok(f"已添加 {len(proxies)} 个节点 (新增 {added})")

    elif action == "update":
        subs = load_subscriptions()
        sub_list = subs.get("subscriptions", [])
        if not sub_list:
            _warn("没有订阅")
            return

        cfg = load_config()
        all_new_proxies = []
        for sub in sub_list:
            url = sub.get("url", "")
            _info(f"更新 {sub.get('name', url[:30])}...")
            try:
                proxies = parse_subscription(url)
                all_new_proxies.extend(proxies)
                sub["proxy_count"] = len(proxies)
                sub["last_update"] = datetime.now().isoformat()
                _ok(f"  {len(proxies)} 个节点")
            except Exception as e:
                _err(f"  失败: {e}")

        if all_new_proxies:
            cfg["proxies"] = all_new_proxies
            from .data import save_config
            save_config(cfg)
            save_subscriptions(subs)

            # Update proxy groups
            from .proxy import apply_mode
            mode = detect_current_mode()
            apply_mode(mode)
            _ok(f"共 {len(all_new_proxies)} 个节点已更新")

    elif action == "list":
        subs = load_subscriptions()
        sub_list = subs.get("subscriptions", [])
        if not sub_list:
            _print("\n  没有订阅\n")
            return
        _print()
        for s in sub_list:
            _print(f"  {_dim('•')} {s.get('name', '?')}  {s.get('proxy_count', 0)} nodes  {_dim(time_ago(s.get('last_update')))}")
            _print(f"    {C_DIM}{s.get('url', '?')[:60]}{C_RESET}")
        _print()

    elif action == "remove":
        if len(args) < 2:
            _err("请提供订阅名称")
            return
        name = args[1]
        subs = load_subscriptions()
        sub_list = subs.get("subscriptions", [])
        before = len(sub_list)
        sub_list = [s for s in sub_list if s.get("name") != name]
        if len(sub_list) == before:
            _err(f"未找到订阅: {name}")
            return
        subs["subscriptions"] = sub_list
        save_subscriptions(subs)
        _ok(f"已删除订阅: {name}")


def cmd_node(args: list[str]):
    """Select node: /node <name>"""
    if not args:
        # List available nodes
        try:
            groups = get_proxy_groups()
            _print()
            for g in groups:
                if g.is_group:
                    _print(f"  {C_BOLD}{g.name}{C_RESET} ({g.group_type})")
                    if g.current:
                        _print(f"    当前: {_green(g.current)}")
                    for m in g.members:
                        marker = " →" if m == g.current else "  "
                        _print(f"    {marker} {m}")
                    _print()
        except Exception as e:
            _err(f"获取节点失败: {e}")
        return

    node_name = " ".join(args)
    try:
        api = ClashAPI()
        # Find which group this node belongs to
        groups = get_proxy_groups()
        found = False
        for g in groups:
            if g.is_group and node_name in g.members:
                api.switch_proxy(g.name, node_name)
                _ok(f"已切换到 {node_name} (组: {g.name})")
                found = True
                break

        if not found:
            # Try direct switch on GLOBAL group
            try:
                api.switch_proxy("GLOBAL", node_name)
                _ok(f"已切换到 {node_name}")
            except Exception:
                _err(f"未找到节点: {node_name}")
                _info("用 clashctl /node 查看可用节点")
    except Exception as e:
        _err(f"切换失败: {e}")


def cmd_test(args: list[str]):
    """Speed test: /test [node_name]"""
    _info("测速中...")
    try:
        if args:
            node_name = " ".join(args)
            # Test single node
            results = speed_test([node_name])
        else:
            # Test all nodes
            cfg = load_config()
            names = [p.get("name", "") for p in cfg.get("proxies", []) if p.get("name")]
            if not names:
                _warn("没有节点可测试")
                return
            results = speed_test(names)

        _print()
        for name, delay in sorted(results.items(), key=lambda x: x[1] if x[1] > 0 else 99999):
            if delay > 0:
                _print(f"  {_green('●')} {name}: {delay}ms")
            else:
                _print(f"  {_red('○')} {name}: {_dim('timeout')}")
        _print()
    except Exception as e:
        _err(f"测速失败: {e}")


def cmd_restart():
    """Restart mihomo."""
    _info("重启 mihomo...")
    if restart():
        _ok("已重启")
    else:
        _err("重启失败")


def cmd_help():
    """Show help."""
    _print()
    _print(f"  {C_BOLD}clashctl{C_RESET} — qubes-clash-gateway 控制器")
    _print(f"  {'─' * 40}")
    _print(f"  /status              查看状态")
    _print(f"  /mode global|rule|direct  切换模式")
    _print(f"  /sub add <url>       添加订阅")
    _print(f"  /sub update          更新所有订阅")
    _print(f"  /sub list            列出订阅")
    _print(f"  /sub remove <name>   删除订阅")
    _print(f"  /node                列出所有节点")
    _print(f"  /node <name>         选择节点")
    _print(f"  /test [node]         测速")
    _print(f"  /dns fake-ip|redir-host  切换 DNS 模式")
    _print(f"  /restart             重启 mihomo")
    _print(f"  /help                显示帮助")
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
            _print(f"\n  用法: clashctl /dns fake-ip|redir-host\n")
        else:
            if apply_dns_preset(args[1]):
                _ok(f"DNS 已切换到 {args[1]}")
            else:
                _err(f"无效 DNS 模式: {args[1]}")
    elif cmd in ("/restart", "restart"):
        cmd_restart()
    elif cmd in ("/help", "help", "--help", "-h"):
        cmd_help()
    else:
        _err(f"未知命令: {cmd}")
        _info("用 clashctl /help 查看帮助")
