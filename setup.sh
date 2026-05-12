#!/bin/bash
# qubes-clash-gateway one-click install script
# Turns a Qubes NetVM into a transparent proxy gateway, AppVMs use proxy with zero config
set -euo pipefail

REPO_URL="https://github.com/iasds/qubes-clash-gateway.git"
INSTALL_DIR="/opt/qubes-clash-gateway"
GITHUB_REPO="MetaCubeX/mihomo"
MIHOMO_BIN="/usr/local/bin/mihomo"
CONFIG_DIR="/rw/config/clash"
DNS_PORT=1053           # mihomo DNS listen port (avoid port 53 to prevent loop)
API_PORT=9090           # mihomo external control port

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[✗]${NC} $*"; exit 1; }
step()  { echo -e "\n${CYAN}[$1/$TOTAL_STEPS]${NC} $2"; }

TOTAL_STEPS=6

# ==================== 1. Environment Check ====================
step 1 "Checking environment"
[ "$(id -u)" -eq 0 ] || error "Please run this script with sudo"
command -v git >/dev/null || error "git is required (apt install git)"
command -v curl >/dev/null || error "curl is required (apt install curl)"
command -v python3 >/dev/null || error "python3 is required (apt install python3)"
command -v nft >/dev/null || error "nftables is required (apt install nftables)"
info "Environment check passed"

# ==================== 2. Clone/Update Repository ====================
step 2 "Fetching project code"
if [ -d "$INSTALL_DIR/.git" ]; then
    info "Updating existing installation: $INSTALL_DIR"
    cd "$INSTALL_DIR"
    git pull --ff-only 2>/dev/null || warn "git pull failed, using existing code"
else
    info "Cloning repository to $INSTALL_DIR"
    git clone "$REPO_URL" "$INSTALL_DIR" 2>/dev/null || {
        warn "git clone failed, trying zip download..."
        curl -fSL -o /tmp/qcg.zip \
            "https://github.com/iasds/qubes-clash-gateway/archive/refs/heads/master.zip" \
            --connect-timeout 15 || error "Download failed. Please ensure git credentials are configured or clone manually."
        mkdir -p "$INSTALL_DIR"
        unzip -qo /tmp/qcg.zip -d /tmp/qcg-extract
        cp -r /tmp/qcg-extract/qubes-clash-gateway-master/* "$INSTALL_DIR/"
        rm -rf /tmp/qcg.zip /tmp/qcg-extract
        cd "$INSTALL_DIR"
        git init && git add -A && git commit -m "initial" 2>/dev/null || true
    }
fi
info "Code ready: $INSTALL_DIR"

# ==================== 3. Download mihomo ====================
step 3 "Downloading mihomo"
if [ -f "$MIHOMO_BIN" ]; then
    info "mihomo already exists: $MIHOMO_BIN"
else
    DOWNLOADED=0
    for candidate in /tmp/mihomo /tmp/mihomo.gz "$INSTALL_DIR/mihomo" "$INSTALL_DIR/mihomo.gz"; do
        if [ -f "$candidate" ]; then
            if [[ "$candidate" == *.gz ]]; then
                gunzip -c "$candidate" > "$MIHOMO_BIN"
            else
                cp "$candidate" "$MIHOMO_BIN"
            fi
            chmod +x "$MIHOMO_BIN"
            info "Installed from local: $candidate"
            DOWNLOADED=1
            break
        fi
    done

    if [ "$DOWNLOADED" -eq 0 ]; then
        info "Downloading from GitHub..."
        local_url=$(curl -sf --connect-timeout 10 \
            "https://api.github.com/repos/${GITHUB_REPO}/releases?per_page=5" | \
            python3 -c "
import json, sys
try:
    for r in json.load(sys.stdin):
        for a in r.get('assets', []):
            n = a['name'].lower()
            if 'linux' in n and 'amd64' in n and n.endswith('.gz'):
                print(a['browser_download_url']); sys.exit(0)
except: pass
" 2>/dev/null) || true

        if [ -n "$local_url" ]; then
            if curl -fL --connect-timeout 20 -o /tmp/mihomo.gz "$local_url"; then
                gunzip -c /tmp/mihomo.gz > "$MIHOMO_BIN"
                chmod +x "$MIHOMO_BIN"
                rm -f /tmp/mihomo.gz
                info "Download complete"
            else
                error "Download failed. Please manually download mihomo to /tmp/mihomo.gz:\n  https://github.com/MetaCubeX/mihomo/releases\n  Select the linux-amd64 .gz file"
            fi
        else
            error "Unable to get download link. Please download manually:\n  https://github.com/MetaCubeX/mihomo/releases\n  Select the linux-amd64 .gz file, place at /tmp/mihomo.gz"
        fi
    fi
fi
"$MIHOMO_BIN" -v 2>/dev/null && true

# ==================== 4. Install Configuration ====================
step 4 "Installing configuration"
mkdir -p "$CONFIG_DIR"

if [ ! -f "$CONFIG_DIR/config.yaml" ]; then
    cp "$INSTALL_DIR/config/config.yaml" "$CONFIG_DIR/config.yaml"
    info "Config template copied to $CONFIG_DIR/config.yaml"
    warn "Please edit $CONFIG_DIR/config.yaml to add proxy nodes, then restart the service"
else
    info "Config already exists, skipping"
fi

# Install clashctl to PATH
CLASHCTL_BIN="/usr/local/bin/clashctl"
cat > "$CLASHCTL_BIN" << 'CLASHEOF'
#!/bin/bash
# clashctl — qubes-clash-gateway terminal controller
exec python3 -m clashctl "$@"
CLASHEOF
chmod +x "$CLASHCTL_BIN"
# Link clashctl package
if [ -d "$INSTALL_DIR/clashctl" ]; then
    ln -sf "$INSTALL_DIR/clashctl" "$(python3 -c 'import site; print(site.getsitepackages()[0])')/clashctl" 2>/dev/null || true
fi
info "clashctl installed"

# systemd service
cat > /etc/systemd/system/mihomo.service << UNIT
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
systemctl enable mihomo
info "systemd service created"

# sudoers — allow passwordless mihomo restart for user
SUDOERS_FILE="/etc/sudoers.d/clashctl"
cp "$INSTALL_DIR/config/sudoers-clashctl" "$SUDOERS_FILE"
chmod 440 "$SUDOERS_FILE"
info "sudoers configured (passwordless mihomo restart)"

# ==================== 5. nftables Transparent Proxy Rules ====================
step 5 "Configuring nftables transparent proxy"

# Write persistent nftables script
NFT_SCRIPT="/rw/config/clash/nftables-proxy.sh"
cat > "$NFT_SCRIPT" << 'NFTEOF'
#!/bin/bash
# qubes-clash-gateway nftables transparent proxy rules
# Core idea: Disable mihomo's dns-hijack/auto-redirect, manually hijack AppVM traffic
# This way mihomo's own DNS queries won't be hijacked back to TUN, fully resolving DNS loops

set -euo pipefail

DNS_PORT=1053    # mihomo DNS listen port
TABLE_NAME="qcg_proxy"

# Clean old rules
nft delete table inet "$TABLE_NAME" 2>/dev/null || true

nft add table inet "$TABLE_NAME"

# ── Set: AppVM vif interfaces ──
nft add set inet "$TABLE_NAME" vif_interfaces '{ type ifname; }'
# Dynamically populate vif interfaces
for iface in /sys/class/net/vif*; do
    [ -d "$iface" ] && nft add element inet "$TABLE_NAME" vif_interfaces "{ $(basename $iface) }" 2>/dev/null || true
done

# ── Chain: AppVM traffic hijack ──
nft add chain inet "$TABLE_NAME" appvm_prerouting '{ type nat hook prerouting priority -100; policy accept; }'

# Only hijack traffic from AppVM interfaces
nft add rule inet "$TABLE_NAME" appvm_prerouting iifname @vif_interfaces udp dport 53 \
    redirect to :$DNS_PORT
nft add rule inet "$TABLE_NAME" appvm_prerouting iifname @vif_interfaces tcp dport 53 \
    redirect to :$DNS_PORT

# ── Exclude proxy server IPs (avoid loops) ──
# Users should configure in config.yaml route-exclude-address
# Common private network ranges excluded here, proxy server IPs handled by mihomo TUN route-exclude-address

echo "[✓] nftables transparent proxy rules loaded"
echo "    DNS: AppVM:53 → localhost:${DNS_PORT}"
echo "    TCP/UDP: Handled by mihomo TUN auto-route"
NFTEOF
chmod +x "$NFT_SCRIPT"

# Load nftables rules
bash "$NFT_SCRIPT"
info "nftables rules loaded"

# qubes-firewall-user-script — auto-reload nftables when VMs connect
FW_SCRIPT="/rw/config/qubes-firewall-user-script"
cat > "$FW_SCRIPT" << 'FWEOF'
#!/bin/sh
# Auto-load nftables transparent proxy rules when VMs connect
/rw/config/clash/nftables-proxy.sh
FWEOF
chmod +x "$FW_SCRIPT"
info "qubes-firewall-user-script configured"

# systemd path unit — monitor new vif interfaces and auto-reload
cat > /etc/systemd/system/qcg-vif-monitor.service << 'SVCEOF'
[Unit]
Description=QCG VIF Interface Monitor
After=network.target

[Service]
Type=oneshot
ExecStart=/rw/config/clash/nftables-proxy.sh
SVCEOF

cat > /etc/systemd/system/qcg-vif-monitor.path << 'PATHEOF'
[Unit]
Description=Monitor new VIF interfaces

[Path]
PathModified=/sys/class/net
MakeDirectory=yes

[Install]
WantedBy=multi-user.target
PATHEOF

systemctl daemon-reload
systemctl enable --now qcg-vif-monitor.path 2>/dev/null || true
info "VIF monitor service started"

# rc.local — persistence
RCLOCAL="/rw/config/rc.local"
# First clean old qcg config
if [ -f "$RCLOCAL" ]; then
    sed -i '/# === qubes-clash-gateway/,/# === end qubes-clash-gateway/d' "$RCLOCAL"
fi

cat >> "$RCLOCAL" << 'RCEOF'

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
chmod +x "$RCLOCAL"
info "rc.local configured (auto-restore on reboot)"

# ==================== 6. Start ====================
step 6 "Starting service"
systemctl restart mihomo 2>/dev/null || true
sleep 2

if systemctl is-active --quiet mihomo; then
    info "mihomo is running"
else
    warn "mihomo not started (may need to configure nodes first)"
fi

# Done
GATEWAY_IP=$(ip -4 addr show eth0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' || echo "?")
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║   qubes-clash-gateway installation complete!     ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "  Config:  $CONFIG_DIR/config.yaml"
echo "  DNS:     ${GATEWAY_IP}:${DNS_PORT} (fake-ip)"
echo "  API:     127.0.0.1:${API_PORT}"
echo ""
echo "  Management commands:"
echo "    clashctl /status       # Show status"
echo "    clashctl /mode rule    # Rule-based routing"
echo "    clashctl /mode global  # Global proxy"
echo "    clashctl /mode direct  # Direct connection"
echo "    clashctl /sub add <url>  # Add subscription"
echo "    clashctl /node <name>  # Select node"
echo ""
echo "  Next steps:"
echo "    1. Edit config to add nodes: nano $CONFIG_DIR/config.yaml"
echo "    2. Restart: systemctl restart mihomo"
echo "    3. dom0: qvm-prefs <appvm> netvm $(hostname)"
echo "    4. Test: curl -x socks5://127.0.0.1:7890 https://api.ipify.org"
echo ""
echo "  Logs: journalctl -u mihomo -f"
echo "  Uninstall: bash $INSTALL_DIR/uninstall.sh"
echo ""
