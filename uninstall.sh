#!/bin/bash
# qubes-clash-gateway uninstall script
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }

CONFIG_DIR="/rw/config/clash"
MIHOMO_BIN="/usr/local/bin/mihomo"
SERVICE_NAME="mihomo"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   qubes-clash-gateway Uninstaller        ║"
echo "╚══════════════════════════════════════════╝"
echo ""

[ "$(id -u)" -eq 0 ] || { echo -e "${RED}[✗]${NC} Please run with sudo"; exit 1; }

# Stop and remove service
if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    systemctl stop "$SERVICE_NAME"
    info "Stopped mihomo"
fi
if [ -f "/etc/systemd/system/${SERVICE_NAME}.service" ]; then
    systemctl disable "$SERVICE_NAME" 2>/dev/null || true
    rm -f "/etc/systemd/system/${SERVICE_NAME}.service"
    systemctl daemon-reload
    info "Removed systemd service"
fi

# Remove binary
if [ -f "$MIHOMO_BIN" ]; then
    rm -f "$MIHOMO_BIN"
    info "Removed $MIHOMO_BIN"
fi

# Clean up clash config section from rc.local
RCLOCAL="/rw/config/rc.local"
if [ -f "$RCLOCAL" ] && grep -q "qubes-clash-gateway" "$RCLOCAL" 2>/dev/null; then
    # Delete content between start and end markers
    sed -i '/# === qubes-clash-gateway ===/,/# === end qubes-clash-gateway ===/d' "$RCLOCAL"
    info "Cleaned up rc.local"
fi

# Clean up nftables rules
nft delete table inet qcg_proxy 2>/dev/null || true
nft delete table inet mihomo 2>/dev/null || true
nft delete table inet clash 2>/dev/null || true
info "Cleaned up nftables rules"

# Clean up clashctl
rm -f /usr/local/bin/clashctl
info "Cleaned up clashctl"

# Clean up sudoers
rm -f /etc/sudoers.d/clashctl
info "Cleaned up sudoers"

# Ask whether to delete config
echo ""
read -p "Delete config directory $CONFIG_DIR? [y/N] " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -rf "$CONFIG_DIR"
    info "Removed $CONFIG_DIR"
else
    info "Kept $CONFIG_DIR"
fi

echo ""
info "Uninstall complete. AppVMs will no longer have internet through this NetVM. Please switch NetVM in dom0."
