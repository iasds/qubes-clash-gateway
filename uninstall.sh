#!/bin/bash
# qubes-clash-gateway uninstall script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/scripts/lib.sh"

CONFIG_DIR="/rw/config/clash"
MIHOMO_BIN="/usr/local/bin/mihomo"
SERVICE_NAME="mihomo"
VERIFY_ONLY=false

# Parse args
if [[ "${1:-}" == "--verify" ]]; then
    VERIFY_ONLY=true
fi

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   qubes-clash-gateway Uninstaller        ║"
echo "╚══════════════════════════════════════════╝"
echo ""

require_root

if $VERIFY_ONLY; then
    echo "Checking for remaining artifacts..."
    ISSUES=0

    if pgrep -x mihomo &>/dev/null; then
        log_error "mihomo process still running"
        ISSUES=$((ISSUES + 1))
    else
        log_info "No mihomo process running"
    fi

    if [ -f "/etc/systemd/system/${SERVICE_NAME}.service" ]; then
        log_error "Systemd unit still exists: /etc/systemd/system/${SERVICE_NAME}.service"
        ISSUES=$((ISSUES + 1))
    else
        log_info "Systemd unit removed"
    fi

    if [ -f "$MIHOMO_BIN" ]; then
        log_error "Binary still exists: $MIHOMO_BIN"
        ISSUES=$((ISSUES + 1))
    else
        log_info "Binary removed"
    fi

    if nft list table inet qcg_proxy &>/dev/null; then
        log_error "nftables table qcg_proxy still exists"
        ISSUES=$((ISSUES + 1))
    else
        log_info "nftables table qcg_proxy removed"
    fi

    if [ -f /etc/sudoers.d/clashctl ]; then
        log_error "Sudoers entry still exists: /etc/sudoers.d/clashctl"
        ISSUES=$((ISSUES + 1))
    else
        log_info "Sudoers entry removed"
    fi

    if [ -f /usr/local/bin/clashctl ]; then
        log_error "clashctl binary still exists"
        ISSUES=$((ISSUES + 1))
    else
        log_info "clashctl binary removed"
    fi

    if [ -f /etc/systemd/system/qcg-vif-monitor.path ]; then
        log_error "VIF monitor unit still exists"
        ISSUES=$((ISSUES + 1))
    else
        log_info "VIF monitor unit removed"
    fi

    echo ""
    if [ "$ISSUES" -eq 0 ]; then
        log_info "All clean! No artifacts remaining."
        exit 0
    else
        log_error "$ISSUES artifact(s) remaining. Run uninstall.sh without --verify to clean up."
        exit 1
    fi
fi

# Stop and remove service
if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    systemctl stop "$SERVICE_NAME" || log_error "Failed to stop $SERVICE_NAME"
    log_info "Stopped mihomo"
fi
if [ -f "/etc/systemd/system/${SERVICE_NAME}.service" ]; then
    systemctl disable "$SERVICE_NAME" 2>/dev/null || true
    rm -f "/etc/systemd/system/${SERVICE_NAME}.service"
    systemctl daemon-reload
    log_info "Removed systemd service"
fi

# Remove binary
if [ -f "$MIHOMO_BIN" ]; then
    rm -f "$MIHOMO_BIN"
    log_info "Removed $MIHOMO_BIN"
fi

# Clean up clash config section from rc.local
RCLOCAL="/rw/config/rc.local"
if [ -f "$RCLOCAL" ] && grep -q "qubes-clash-gateway" "$RCLOCAL" 2>/dev/null; then
    sed -i '/# === qubes-clash-gateway ===/,/# === end qubes-clash-gateway ===/d' "$RCLOCAL"
    log_info "Cleaned up rc.local"
fi

# Clean up nftables rules
nft delete table inet qcg_proxy 2>/dev/null || true
nft delete table inet mihomo 2>/dev/null || true
nft delete table inet clash 2>/dev/null || true

# Clean up kill switch rules from qubes-firewall forward chain
for handle in $(nft -a list chain ip qubes-firewall forward 2>/dev/null | grep -E "vif.*dport|vif.*icmp" | awk '{print $NF}'); do
    nft delete rule ip qubes-firewall forward handle "$handle" 2>/dev/null || true
done
log_info "Cleaned up nftables rules (including kill switch)"

# Clean up clashctl
rm -f /usr/local/bin/clashctl
log_info "Cleaned up clashctl"

# Clean up sudoers
rm -f /etc/sudoers.d/clashctl
log_info "Cleaned up sudoers"

# Clean up VIF monitor systemd units
systemctl disable --now qcg-vif-monitor.path 2>/dev/null || true
rm -f /etc/systemd/system/qcg-vif-monitor.path
rm -f /etc/systemd/system/qcg-vif-monitor.service
systemctl daemon-reload 2>/dev/null || true
log_info "Cleaned up VIF monitor"

# Ask whether to delete config
echo ""
read -p "Delete config directory $CONFIG_DIR? [y/N] " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -rf "$CONFIG_DIR"
    log_info "Removed $CONFIG_DIR"
else
    log_info "Kept $CONFIG_DIR"
fi

# Post-uninstall verification
echo ""
echo "Verifying cleanup..."
ISSUES=0
pgrep -x mihomo &>/dev/null && { log_error "mihomo still running!"; ISSUES=$((ISSUES + 1)); }
[ -f "/etc/systemd/system/${SERVICE_NAME}.service" ] && { log_error "Systemd unit still exists!"; ISSUES=$((ISSUES + 1)); }
[ -f "$MIHOMO_BIN" ] && { log_error "Binary still exists!"; ISSUES=$((ISSUES + 1)); }
nft list table inet qcg_proxy &>/dev/null && { log_error "nftables table still exists!"; ISSUES=$((ISSUES + 1)); }
[ -f /etc/sudoers.d/clashctl ] && { log_error "Sudoers still exists!"; ISSUES=$((ISSUES + 1)); }

if [ "$ISSUES" -gt 0 ]; then
    log_error "$ISSUES artifact(s) remaining after cleanup!"
    exit 1
fi

echo ""
log_info "Uninstall complete. All artifacts removed."
echo "  AppVMs will no longer have internet through this NetVM."
echo "  Please switch NetVM in dom0: qvm-prefs <appvm> netvm <other-netvm>"
