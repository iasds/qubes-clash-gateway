"""Simple i18n module for clashctl — hardcoded zh/en translations.

Usage:
    from .i18n import t, set_lang, get_lang

    # In TUI code:
    print(t("title_main"))
    print(t("mode_rule"))

    # Or with format args:
    print(t("nodes_count", count=5))
"""

# Current language (default: zh)
_LANG = "zh"

# ── Translation tables ──────────────────────────────────────────────

_translations: dict[str, dict[str, str]] = {
    # ── General / UI chrome ──
    "title_main": {
        "zh": "Qubes Clash 管理工具",
        "en": "Qubes Clash Gateway Manager",
    },
    "version": {
        "zh": "版本",
        "en": "Version",
    },
    "quit": {
        "zh": "退出",
        "en": "Quit",
    },
    "back": {
        "zh": "返回",
        "en": "Back",
    },
    "cancel": {
        "zh": "取消",
        "en": "Cancel",
    },
    "confirm": {
        "zh": "确认",
        "en": "Confirm",
    },
    "yes": {
        "zh": "是",
        "en": "Yes",
    },
    "no": {
        "zh": "否",
        "en": "No",
    },
    "ok": {
        "zh": "确定",
        "en": "OK",
    },
    "error": {
        "zh": "错误",
        "en": "Error",
    },
    "success": {
        "zh": "成功",
        "en": "Success",
    },
    "loading": {
        "zh": "加载中…",
        "en": "Loading…",
    },
    "please_wait": {
        "zh": "请稍候…",
        "en": "Please wait…",
    },
    "no_data": {
        "zh": "无数据",
        "en": "No data",
    },
    "unknown": {
        "zh": "未知",
        "en": "Unknown",
    },
    "never": {
        "zh": "从未",
        "en": "Never",
    },
    "n_a": {
        "zh": "N/A",
        "en": "N/A",
    },
    "enabled": {
        "zh": "已启用",
        "en": "Enabled",
    },
    "disabled": {
        "zh": "已禁用",
        "en": "Disabled",
    },

    # ── Time strings ──
    "seconds_ago": {
        "zh": "{n}秒前",
        "en": "{n}s ago",
    },
    "minutes_ago": {
        "zh": "{n}分钟前",
        "en": "{n}m ago",
    },
    "hours_ago": {
        "zh": "{n}h前",
        "en": "{n}h ago",
    },
    "days_ago": {
        "zh": "{n}天前",
        "en": "{n}d ago",
    },

    # ── Menu items ──
    "menu_status": {
        "zh": "状态概览",
        "en": "Status Overview",
    },
    "menu_nodes": {
        "zh": "节点管理",
        "en": "Node Management",
    },
    "menu_mode": {
        "zh": "代理模式",
        "en": "Proxy Mode",
    },
    "menu_rules": {
        "zh": "分流规则",
        "en": "Routing Rules",
    },
    "menu_dns": {
        "zh": "DNS 设置",
        "en": "DNS Settings",
    },
    "menu_subscriptions": {
        "zh": "订阅管理",
        "en": "Subscriptions",
    },
    "menu_speedtest": {
        "zh": "测速",
        "en": "Speed Test",
    },
    "menu_settings": {
        "zh": "设置",
        "en": "Settings",
    },
    "menu_language": {
        "zh": "语言/Language",
        "en": "Language/语言",
    },
    "menu_logs": {
        "zh": "日志",
        "en": "Logs",
    },
    "menu_connections": {
        "zh": "连接",
        "en": "Connections",
    },

    # ── Status ──
    "status_running": {
        "zh": "运行中",
        "en": "Running",
    },
    "status_stopped": {
        "zh": "已停止",
        "en": "Stopped",
    },
    "status_active": {
        "zh": "活跃",
        "en": "Active",
    },
    "uptime": {
        "zh": "运行时间",
        "en": "Uptime",
    },
    "memory_usage": {
        "zh": "内存占用",
        "en": "Memory",
    },
    "connections_count": {
        "zh": "连接数",
        "en": "Connections",
    },
    "traffic_upload": {
        "zh": "上传",
        "en": "Upload",
    },
    "traffic_download": {
        "zh": "下载",
        "en": "Download",
    },

    # ── Proxy mode ──
    "mode_rule": {
        "zh": "规则模式",
        "en": "Rule Mode",
    },
    "mode_global": {
        "zh": "全局模式",
        "en": "Global Mode",
    },
    "mode_direct": {
        "zh": "直连模式",
        "en": "Direct Mode",
    },
    "current_mode": {
        "zh": "当前模式",
        "en": "Current Mode",
    },
    "mode_switched": {
        "zh": "已切换到{mode}模式",
        "en": "Switched to {mode} mode",
    },

    # ── Nodes ──
    "node_select": {
        "zh": "选择节点",
        "en": "Select Node",
    },
    "node_current": {
        "zh": "当前节点",
        "en": "Current Node",
    },
    "node_test_latency": {
        "zh": "测试延迟",
        "en": "Test Latency",
    },
    "node_latency": {
        "zh": "延迟",
        "en": "Latency",
    },
    "node_timeout": {
        "zh": "超时",
        "en": "Timeout",
    },
    "nodes_count": {
        "zh": "共 {count} 个节点",
        "en": "{count} nodes",
    },
    "node_type": {
        "zh": "类型",
        "en": "Type",
    },

    # ── Rules ──
    "rule_preset": {
        "zh": "规则预设",
        "en": "Rule Preset",
    },
    "rule_preset_smart_split": {
        "zh": "智能分流",
        "en": "Smart Split",
    },
    "rule_preset_smart_split_desc": {
        "zh": "中国直连，国外自动选节点",
        "en": "China direct, overseas auto-select node",
    },
    "rule_preset_all_proxy": {
        "zh": "全部代理",
        "en": "All Proxy",
    },
    "rule_preset_all_proxy_desc": {
        "zh": "所有流量走自动选节点",
        "en": "All traffic through auto-select node",
    },
    "rule_preset_bypass_cn": {
        "zh": "仅代理受限",
        "en": "Bypass CN",
    },
    "rule_preset_bypass_cn_desc": {
        "zh": "只代理已知受限站点",
        "en": "Only proxy known blocked sites",
    },
    "rules_applied": {
        "zh": "已应用规则",
        "en": "Rules Applied",
    },

    # ── DNS ──
    "dns_preset": {
        "zh": "DNS 预设",
        "en": "DNS Preset",
    },
    "dns_fake_ip": {
        "zh": "Fake-IP（推荐）",
        "en": "Fake-IP (Recommended)",
    },
    "dns_fake_ip_desc": {
        "zh": "防DNS污染，CN域名fallback直连",
        "en": "Anti DNS pollution, CN domains fallback to direct",
    },
    "dns_redir_host": {
        "zh": "Redir-Host",
        "en": "Redir-Host",
    },
    "dns_redir_host_desc": {
        "zh": "传统模式，兼容性好",
        "en": "Legacy mode, good compatibility",
    },
    "dns_mode": {
        "zh": "DNS 模式",
        "en": "DNS Mode",
    },

    # ── Subscriptions ──
    "sub_add": {
        "zh": "添加订阅",
        "en": "Add Subscription",
    },
    "sub_update": {
        "zh": "更新订阅",
        "en": "Update Subscription",
    },
    "sub_update_all": {
        "zh": "更新全部",
        "en": "Update All",
    },
    "sub_delete": {
        "zh": "删除订阅",
        "en": "Delete Subscription",
    },
    "sub_name": {
        "zh": "名称",
        "en": "Name",
    },
    "sub_url": {
        "zh": "URL",
        "en": "URL",
    },
    "sub_last_update": {
        "zh": "最后更新",
        "en": "Last Updated",
    },
    "sub_node_count": {
        "zh": "节点数",
        "en": "Node Count",
    },
    "sub_updating": {
        "zh": "正在更新订阅…",
        "en": "Updating subscription…",
    },
    "sub_updated": {
        "zh": "订阅更新成功",
        "en": "Subscription updated successfully",
    },
    "sub_update_failed": {
        "zh": "订阅更新失败",
        "en": "Subscription update failed",
    },
    "sub_empty": {
        "zh": "暂无订阅，按 [a] 添加",
        "en": "No subscriptions, press [a] to add",
    },
    "sub_enter_url": {
        "zh": "请输入订阅 URL：",
        "en": "Enter subscription URL:",
    },
    "sub_enter_name": {
        "zh": "请输入订阅名称：",
        "en": "Enter subscription name:",
    },

    # ── Speed test ──
    "speedtest_start": {
        "zh": "开始测速",
        "en": "Start Speed Test",
    },
    "speedtest_testing": {
        "zh": "正在测速…",
        "en": "Testing…",
    },
    "speedtest_done": {
        "zh": "测速完成",
        "en": "Speed Test Complete",
    },
    "speedtest_ms": {
        "zh": "{ms}ms",
        "en": "{ms}ms",
    },

    # ── Config management ──
    "config_generate": {
        "zh": "生成配置",
        "en": "Generate Config",
    },
    "config_generated": {
        "zh": "配置已生成",
        "en": "Config Generated",
    },
    "config_apply": {
        "zh": "应用配置",
        "en": "Apply Config",
    },
    "config_applied": {
        "zh": "配置已应用",
        "en": "Config Applied",
    },
    "config_backup": {
        "zh": "备份配置",
        "en": "Backup Config",
    },
    "config_restore": {
        "zh": "恢复配置",
        "en": "Restore Config",
    },
    "config_reset": {
        "zh": "重置配置",
        "en": "Reset Config",
    },
    "config_reset_confirm": {
        "zh": "确认重置所有配置？",
        "en": "Reset all configuration?",
    },

    # ── Service control ──
    "service_start": {
        "zh": "启动服务",
        "en": "Start Service",
    },
    "service_stop": {
        "zh": "停止服务",
        "en": "Stop Service",
    },
    "service_restart": {
        "zh": "重启服务",
        "en": "Restart Service",
    },
    "service_restarted": {
        "zh": "服务已重启",
        "en": "Service restarted",
    },
    "service_starting": {
        "zh": "正在启动…",
        "en": "Starting…",
    },
    "service_stopping": {
        "zh": "正在停止…",
        "en": "Stopping…",
    },

    # ── Errors / Messages ──
    "err_api_unreachable": {
        "zh": "无法连接到 mihomo API",
        "en": "Cannot reach mihomo API",
    },
    "err_api_check": {
        "zh": "请检查 mihomo 是否运行中",
        "en": "Please check if mihomo is running",
    },
    "err_config_not_found": {
        "zh": "配置文件不存在",
        "en": "Config file not found",
    },
    "err_invalid_url": {
        "zh": "无效的 URL",
        "en": "Invalid URL",
    },
    "err_no_nodes": {
        "zh": "没有可用节点",
        "en": "No available nodes",
    },
    "err_permission": {
        "zh": "权限不足",
        "en": "Permission denied",
    },
    "msg_operation_complete": {
        "zh": "操作完成",
        "en": "Operation complete",
    },
    "msg_press_any_key": {
        "zh": "按任意键继续…",
        "en": "Press any key to continue…",
    },
    "msg_press_q_back": {
        "zh": "按 [q] 返回",
        "en": "Press [q] to go back",
    },

    # ── Key hints ──
    "hint_navigation": {
        "zh": "↑↓ 导航  Enter 选择  q 返回",
        "en": "↑↓ Navigate  Enter Select  q Back",
    },
    "hint_edit": {
        "zh": "e 编辑  d 删除  a 添加",
        "en": "e Edit  d Delete  a Add",
    },
    "hint_select": {
        "zh": "↑↓ 选择  Enter 确认  Esc 取消",
        "en": "↑↓ Select  Enter Confirm  Esc Cancel",
    },
    "hint_search": {
        "zh": "/ 搜索",
        "en": "/ Search",
    },
    "hint_filter": {
        "zh": "f 筛选",
        "en": "f Filter",
    },
}


def set_lang(lang: str) -> None:
    """Set the current language ('zh' or 'en')."""
    global _LANG
    if lang in ("zh", "en"):
        _LANG = lang


def get_lang() -> str:
    """Return the current language code."""
    return _LANG


def t(key: str, **kwargs) -> str:
    """Translate a key to the current language.

    Falls back to zh if key is missing in current language,
    then returns the raw key if not found at all.

    Supports optional format kwargs:
        t("nodes_count", count=5)  -> "共 5 个节点"
    """
    entry = _translations.get(key)
    if entry is None:
        return key
    text = entry.get(_LANG) or entry.get("zh") or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text


def available_langs() -> list[str]:
    """Return list of supported language codes."""
    return ["zh", "en"]


# ── Country/region code → human-readable name ───────────────────────

_REGION_NAMES: dict[str, dict[str, str]] = {
    "US": {"zh": "美国", "en": "United States"},
    "CN": {"zh": "中国", "en": "China"},
    "HK": {"zh": "香港", "en": "Hong Kong"},
    "TW": {"zh": "台湾", "en": "Taiwan"},
    "JP": {"zh": "日本", "en": "Japan"},
    "KR": {"zh": "韩国", "en": "South Korea"},
    "SG": {"zh": "新加坡", "en": "Singapore"},
    "DE": {"zh": "德国", "en": "Germany"},
    "GB": {"zh": "英国", "en": "United Kingdom"},
    "FR": {"zh": "法国", "en": "France"},
    "CA": {"zh": "加拿大", "en": "Canada"},
    "AU": {"zh": "澳大利亚", "en": "Australia"},
    "NL": {"zh": "荷兰", "en": "Netherlands"},
    "RU": {"zh": "俄罗斯", "en": "Russia"},
    "IN": {"zh": "印度", "en": "India"},
    "BR": {"zh": "巴西", "en": "Brazil"},
    "TH": {"zh": "泰国", "en": "Thailand"},
    "VN": {"zh": "越南", "en": "Vietnam"},
    "MY": {"zh": "马来西亚", "en": "Malaysia"},
    "ID": {"zh": "印尼", "en": "Indonesia"},
    "PH": {"zh": "菲律宾", "en": "Philippines"},
    "TR": {"zh": "土耳其", "en": "Turkey"},
    "UA": {"zh": "乌克兰", "en": "Ukraine"},
    "IT": {"zh": "意大利", "en": "Italy"},
    "ES": {"zh": "西班牙", "en": "Spain"},
    "SE": {"zh": "瑞典", "en": "Sweden"},
    "CH": {"zh": "瑞士", "en": "Switzerland"},
    "FI": {"zh": "芬兰", "en": "Finland"},
    "NO": {"zh": "挪威", "en": "Norway"},
    "PL": {"zh": "波兰", "en": "Poland"},
    "AR": {"zh": "阿根廷", "en": "Argentina"},
    "MX": {"zh": "墨西哥", "en": "Mexico"},
    "ZA": {"zh": "南非", "en": "South Africa"},
    "AE": {"zh": "阿联酋", "en": "UAE"},
    "IL": {"zh": "以色列", "en": "Israel"},
    "CL": {"zh": "智利", "en": "Chile"},
    "CO": {"zh": "哥伦比亚", "en": "Colombia"},
    "EG": {"zh": "埃及", "en": "Egypt"},
    "IE": {"zh": "爱尔兰", "en": "Ireland"},
    "NZ": {"zh": "新西兰", "en": "New Zealand"},
    "PT": {"zh": "葡萄牙", "en": "Portugal"},
    "RO": {"zh": "罗马尼亚", "en": "Romania"},
    "CZ": {"zh": "捷克", "en": "Czechia"},
    "AT": {"zh": "奥地利", "en": "Austria"},
    "BE": {"zh": "比利时", "en": "Belgium"},
    "DK": {"zh": "丹麦", "en": "Denmark"},
    "HU": {"zh": "匈牙利", "en": "Hungary"},
    "MO": {"zh": "澳门", "en": "Macau"},
}


def get_region_name(code: str) -> str:
    """Return a localised human-readable region/country name for an ISO code.

    Args:
        code: Two-letter ISO country code (e.g. "US", "HK").

    Returns:
        Localised name, or the raw code if unknown.
    """
    if not code:
        return ""
    entry = _REGION_NAMES.get(code.upper())
    if entry is None:
        return code
    return entry.get(_LANG) or entry.get("en") or code
