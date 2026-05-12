#!/bin/bash
# qubes-clash-gateway install script (basic version)
# Tip: Use setup.sh for full installation (with nftables, clashctl, sudoers)
# This script only does basic installation (mihomo + systemd + rc.local)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_DIR="/rw/config/clash"
MIHOMO_BIN="/usr/local/bin/mihomo"
SERVICE_NAME="mihomo"
GITHUB_REPO="MetaCubeX/mihomo"

# Colors
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[✗]${NC} $*"; exit 1; }

# ==================== Check Environment ====================
check_env() {
    [ "$(id -u)" -eq 0 ] || error "Please run with sudo"
    command -v python3 >/dev/null || error "python3 is required"
    info "Environment check passed"
}

# ==================== Download mihomo ====================
download_mihomo() {
    if [ -f "$MIHOMO_BIN" ]; then
        info "mihomo already exists: $MIHOMO_BIN"
        "$MIHOMO_BIN" -v 2>/dev/null || warn "Version check failed, continuing installation"
        return 0
    fi

    # Check for local pre-downloaded files
    for candidate in "$SCRIPT_DIR/mihomo" "$SCRIPT_DIR/mihomo.gz" "/tmp/mihomo" "/tmp/mihomo.gz"; do
        if [ -f "$candidate" ]; then
            if [[ "$candidate" == *.gz ]]; then
                info "Extracting local file: $candidate"
                gunzip -c "$candidate" > "$MIHOMO_BIN"
            else
                info "Copying local file: $candidate"
                cp "$candidate" "$MIHOMO_BIN"
            fi
            chmod +x "$MIHOMO_BIN"
            info "mihomo installation complete"
            return 0
        fi
    done

    # Download from GitHub
    info "Downloading mihomo from GitHub..."
    local api_url="https://api.github.com/repos/${GITHUB_REPO}/releases"
    local download_url=""

    # Try to get linux-amd64 asset from latest release
    download_url=$(curl -sf --connect-timeout 10 "$api_url?per_page=5" | \
        python3 -c "
import json, sys
try:
    releases = json.load(sys.stdin)
    if not isinstance(releases, list):
        sys.exit(1)
    for r in releases:
        for a in r.get('assets', []):
            name = a['name'].lower()
            if 'linux' in name and 'amd64' in name and name.endswith('.gz'):
                print(a['browser_download_url'])
                sys.exit(0)
except:
    pass
" 2>/dev/null) || true

    if [ -n "$download_url" ]; then
        info "Downloading: $download_url"
        if curl -fL --connect-timeout 15 -o /tmp/mihomo.gz "$download_url"; then
            gunzip -c /tmp/mihomo.gz > "$MIHOMO_BIN"
            chmod +x "$MIHOMO_BIN"
            rm -f /tmp/mihomo.gz
            info "mihomo download and installation complete"
            return 0
        fi
        warn "GitHub download failed"
    else
        warn "Unable to get download link (API rate limit or network issue)"
    fi

    # All methods failed
    echo ""
    error "Unable to download mihomo. Please download manually:
  1. Download from another machine: https://github.com/MetaCubeX/mihomo/releases
  2. Select the linux-amd64 .gz file
  3. Transfer to this machine: scp mihomo.gz $(hostname):/tmp/
  4. Re-run this script"
}

# ==================== Create Config Directory ====================
setup_config() {
    mkdir -p "$CONFIG_DIR"

    if [ ! -f "$CONFIG_DIR/config.yaml" ]; then
        info "Copying default config to $CONFIG_DIR/config.yaml"
        cp "$SCRIPT_DIR/config/config.yaml" "$CONFIG_DIR/config.yaml"
    else
        info "Config already exists, skipping ($CONFIG_DIR/config.yaml)"
    fi

    # Ensure non-root user can read/write
    chown -R "$(logname 2>/dev/null || echo user):$(logname 2>/dev/null || echo user)" "$CONFIG_DIR" 2>/dev/null || true
}

# ==================== Create systemd service ====================
setup_service() {
    local service_file="/etc/systemd/system/${SERVICE_NAME}.service"

    info "Creating systemd service"
    cat > "$service_file" << UNIT
[Unit]
Description=mihomo transparent proxy (Qubes gateway)
After=network.target

[Service]
Type=simple
ExecStart=${MIHOMO_BIN} -d ${CONFIG_DIR}
Restart=on-failure
RestartSec=5
LimitNOFILE=infinity

[Install]
WantedBy=multi-user.target
UNIT

    systemctl daemon-reload
    systemctl enable "$SERVICE_NAME"
    info "systemd service created and enabled"
}

# ==================== Set Up Qubes NetVM rc.local ====================
setup_rclocal() {
    local rclocal="/rw/config/rc.local"

    # Backup existing rc.local
    if [ -f "$rclocal" ] && [ -s "$rclocal" ]; then
        cp "$rclocal" "${rclocal}.bak.$(date +%Y%m%d%H%M%S)"
        info "Backed up rc.local"
    fi

    # Check if our config is already present
    if [ -f "$rclocal" ] && grep -q "qubes-clash-gateway" "$rclocal" 2>/dev/null; then
        info "rc.local already contains clash config, skipping"
        return 0
    fi

    info "Appending clash startup config to rc.local"
    cat >> "$rclocal" << 'RCEOF'

# === qubes-clash-gateway ===
# Recreate mihomo systemd service (Qubes AppVMs don't persist /etc/systemd)
if [ ! -f /etc/systemd/system/mihomo.service ]; then
    cat > /etc/systemd/system/mihomo.service << 'SVCEOF'
[Unit]
Description=mihomo Daemon, Another Clash Kernel.
After=network.target NetworkManager.service systemd-networkd.service

[Service]
Type=simple
LimitNPROC=500
LimitNOFILE=1000000
CapabilityBoundingSet=CAP_NET_ADMIN CAP_NET_RAW CAP_NET_BIND_SERVICE CAP_SYS_TIME CAP_SYS_PTRACE CAP_DAC_READ_SEARCH CAP_DAC_OVERRIDE
AmbientCapabilities=CAP_NET_ADMIN CAP_NET_RAW CAP_NET_BIND_SERVICE CAP_SYS_TIME CAP_SYS_PTRACE CAP_DAC_READ_SEARCH CAP_DAC_OVERRIDE
Restart=always
RestartSec=10
ExecStartPre=/usr/local/bin/mihomo -t -d /rw/config/clash
ExecStart=/usr/local/bin/mihomo -d /rw/config/clash
ExecReload=/bin/kill -HUP $MAINPID

[Install]
WantedBy=multi-user.target
SVCEOF
    systemctl daemon-reload
fi

# Ensure clash config dir has correct ownership
chown -R user:user /rw/config/clash/ 2>/dev/null || true

# Start mihomo
systemctl start mihomo 2>/dev/null || true
sleep 2

# Load nftables transparent proxy + Kill Switch rules
bash /rw/config/clash/nftables-proxy.sh 2>/dev/null || true

# Ensure vif interfaces are up
for vif in /sys/class/net/vif*; do
    [ -d "$vif" ] && ip link set "$(basename $vif)" up 2>/dev/null
done

# Auto-add vif interfaces to nftables set (backup in case nftables-proxy.sh missed them)
for vif in /sys/class/net/vif*; do
    [ -d "$vif" ] && nft add element inet qcg_proxy vif_interfaces "{ $(basename $vif) }" 2>/dev/null
done
# === end qubes-clash-gateway ===
RCEOF

    chmod +x "$rclocal"
    info "rc.local configuration complete"
}

# ==================== Start Service ====================
start_service() {
    info "Starting mihomo..."
    systemctl start "$SERVICE_NAME"
    sleep 2

    if systemctl is-active --quiet "$SERVICE_NAME"; then
        info "mihomo is running"
        "$MIHOMO_BIN" -v 2>/dev/null && true
    else
        warn "mihomo failed to start, check logs: journalctl -u $SERVICE_NAME -n 20"
        warn "You may need to configure subscription nodes in $CONFIG_DIR/config.yaml first"
    fi
}

# ==================== Done ====================
print_summary() {
    local ip
    ip=$(ip -4 addr show eth0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' || echo "Unknown")
    echo ""
    echo "=========================================="
    echo "  qubes-clash-gateway installation complete"
    echo "=========================================="
    echo ""
    echo "  Config file: $CONFIG_DIR/config.yaml"
    echo "  Proxy port: 7890 (HTTP/SOCKS5)"
    echo "  DNS port: 1053 (fake-ip)"
    echo "  Gateway address: $ip"
    echo ""
    echo "  Next steps:"
    echo "  1. Add subscription nodes: edit $CONFIG_DIR/config.yaml"
    echo "  2. Restart service: sudo systemctl restart mihomo"
    echo "  3. Test: curl -x socks5h://127.0.0.1:7890 https://www.google.com"
    echo "  4. In dom0, set AppVM: qvm-prefs <appvm> netvm $(hostname)"
    echo ""
    echo "  Management:"
    echo "  - View logs: journalctl -u mihomo -f"
    echo "  - Restart: sudo systemctl restart mihomo"
    echo "  - Uninstall: sudo bash $SCRIPT_DIR/uninstall.sh"
    echo ""
}

# ==================== Main Flow ====================
main() {
    echo ""
    echo "╔══════════════════════════════════════════╗"
    echo "║   qubes-clash-gateway Installer          ║"
    echo "╚══════════════════════════════════════════╝"
    echo ""

    check_env
    download_mihomo
    setup_config
    setup_service
    setup_rclocal
    start_service
    print_summary
}

main "$@"
