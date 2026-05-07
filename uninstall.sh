#!/bin/bash
# qubes-clash-gateway 卸载脚本
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }

CONFIG_DIR="/rw/config/clash"
MIHOMO_BIN="/usr/local/bin/mihomo"
SERVICE_NAME="mihomo"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   qubes-clash-gateway 卸载程序           ║"
echo "╚══════════════════════════════════════════╝"
echo ""

[ "$(id -u)" -eq 0 ] || { echo -e "${RED}[✗]${NC} 请用 sudo 运行"; exit 1; }

# 停止并删除 service
if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    systemctl stop "$SERVICE_NAME"
    info "已停止 mihomo"
fi
if [ -f "/etc/systemd/system/${SERVICE_NAME}.service" ]; then
    systemctl disable "$SERVICE_NAME" 2>/dev/null || true
    rm -f "/etc/systemd/system/${SERVICE_NAME}.service"
    systemctl daemon-reload
    info "已删除 systemd service"
fi

# 删除二进制
if [ -f "$MIHOMO_BIN" ]; then
    rm -f "$MIHOMO_BIN"
    info "已删除 $MIHOMO_BIN"
fi

# 清理 rc.local 中的 clash 配置段
RCLOCAL="/rw/config/rc.local"
if [ -f "$RCLOCAL" ] && grep -q "qubes-clash-gateway" "$RCLOCAL" 2>/dev/null; then
    # 删除从标记开始到结束标记之间的内容
    sed -i '/# === qubes-clash-gateway ===/,/# === end qubes-clash-gateway ===/d' "$RCLOCAL"
    info "已清理 rc.local"
fi

# 清理 nftables 规则（auto-redirect 可能创建的）
nft delete table inet mihomo 2>/dev/null || true
nft delete table inet clash 2>/dev/null || true
info "已清理 nftables 规则"

# 清理 ip rules
ip rule del fwmark 0x162 lookup 2022 2>/dev/null || true
info "已清理 ip rules"

# 询问是否删除配置
echo ""
read -p "是否删除配置目录 $CONFIG_DIR？[y/N] " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -rf "$CONFIG_DIR"
    info "已删除 $CONFIG_DIR"
else
    info "保留 $CONFIG_DIR"
fi

echo ""
info "卸载完成。AppVM 将无法通过此 NetVM 上网，请在 dom0 切换 NetVM。"
