#!/bin/bash
# qubes-clash-gateway 一键安装脚本
# 把 Qubes NetVM 变成透明代理网关，AppVM 零配置走代理
set -euo pipefail

REPO_URL="https://github.com/iasds/qubes-clash-gateway.git"
INSTALL_DIR="/opt/qubes-clash-gateway"
GITHUB_REPO="MetaCubeX/mihomo"
MIHOMO_BIN="/usr/local/bin/mihomo"
CONFIG_DIR="/rw/config/clash"
DNS_PORT=1053           # mihomo DNS 监听端口（不用 53，避免环路）
API_PORT=9090           # mihomo 外部控制端口

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[✗]${NC} $*"; exit 1; }
step()  { echo -e "\n${CYAN}[$1/$TOTAL_STEPS]${NC} $2"; }

TOTAL_STEPS=6

# ==================== 1. 环境检查 ====================
step 1 "检查环境"
[ "$(id -u)" -eq 0 ] || error "请用 sudo 运行此脚本"
command -v git >/dev/null || error "需要 git (apt install git)"
command -v curl >/dev/null || error "需要 curl (apt install curl)"
command -v python3 >/dev/null || error "需要 python3 (apt install python3)"
command -v nft >/dev/null || error "需要 nftables (apt install nftables)"
info "环境检查通过"

# ==================== 2. 克隆/更新仓库 ====================
step 2 "获取项目代码"
if [ -d "$INSTALL_DIR/.git" ]; then
    info "更新已有安装: $INSTALL_DIR"
    cd "$INSTALL_DIR"
    git pull --ff-only 2>/dev/null || warn "git pull 失败，使用已有代码"
else
    info "克隆仓库到 $INSTALL_DIR"
    git clone "$REPO_URL" "$INSTALL_DIR" 2>/dev/null || {
        warn "git clone 失败，尝试下载 zip..."
        curl -fSL -o /tmp/qcg.zip \
            "https://github.com/iasds/qubes-clash-gateway/archive/refs/heads/master.zip" \
            --connect-timeout 15 || error "无法下载。请确保 git 凭据已配置或手动 clone。"
        mkdir -p "$INSTALL_DIR"
        unzip -qo /tmp/qcg.zip -d /tmp/qcg-extract
        cp -r /tmp/qcg-extract/qubes-clash-gateway-master/* "$INSTALL_DIR/"
        rm -rf /tmp/qcg.zip /tmp/qcg-extract
        cd "$INSTALL_DIR"
        git init && git add -A && git commit -m "initial" 2>/dev/null || true
    }
fi
info "代码就绪: $INSTALL_DIR"

# ==================== 3. 下载 mihomo ====================
step 3 "下载 mihomo"
if [ -f "$MIHOMO_BIN" ]; then
    info "mihomo 已存在: $MIHOMO_BIN"
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
            info "从本地安装: $candidate"
            DOWNLOADED=1
            break
        fi
    done

    if [ "$DOWNLOADED" -eq 0 ]; then
        info "从 GitHub 下载..."
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
                info "下载完成"
            else
                error "下载失败。请手动下载 mihomo 到 /tmp/mihomo.gz:\n  https://github.com/MetaCubeX/mihomo/releases\n  选择 linux-amd64 的 .gz 文件"
            fi
        else
            error "无法获取下载链接。请手动下载:\n  https://github.com/MetaCubeX/mihomo/releases\n  选择 linux-amd64 的 .gz 文件，放到 /tmp/mihomo.gz"
        fi
    fi
fi
"$MIHOMO_BIN" -v 2>/dev/null && true

# ==================== 4. 安装配置 ====================
step 4 "安装配置"
mkdir -p "$CONFIG_DIR"

if [ ! -f "$CONFIG_DIR/config.yaml" ]; then
    cp "$INSTALL_DIR/config/config.yaml" "$CONFIG_DIR/config.yaml"
    info "配置模板已复制到 $CONFIG_DIR/config.yaml"
    warn "请编辑 $CONFIG_DIR/config.yaml 添加代理节点后重启服务"
else
    info "配置已存在，跳过"
fi

# clashctl 安装到 PATH
CLASHCTL_BIN="/usr/local/bin/clashctl"
cat > "$CLASHCTL_BIN" << 'CLASHEOF'
#!/bin/bash
# clashctl — qubes-clash-gateway 终端控制器
exec python3 -m clashctl "$@"
CLASHEOF
chmod +x "$CLASHCTL_BIN"
# link clashctl 包
if [ -d "$INSTALL_DIR/clashctl" ]; then
    ln -sf "$INSTALL_DIR/clashctl" "$(python3 -c 'import site; print(site.getsitepackages()[0])')/clashctl" 2>/dev/null || true
fi
info "clashctl 已安装"

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
info "systemd service 已创建"

# sudoers — 允许用户免密重启 mihomo
SUDOERS_FILE="/etc/sudoers.d/clashctl"
cp "$INSTALL_DIR/config/sudoers-clashctl" "$SUDOERS_FILE"
chmod 440 "$SUDOERS_FILE"
info "sudoers 已配置（免密重启 mihomo）"

# ==================== 5. nftables 透明代理规则 ====================
step 5 "配置 nftables 透明代理"

# 写入持久化 nftables 脚本
NFT_SCRIPT="/rw/config/clash/nftables-proxy.sh"
cat > "$NFT_SCRIPT" << 'NFTEOF'
#!/bin/bash
# qubes-clash-gateway nftables 透明代理规则
# 核心思路: 禁用 mihomo 的 dns-hijack/auto-redirect，手动劫持 AppVM 流量
# 这样 mihomo 自己的 DNS 查询不会被劫持回 TUN，彻底解决 DNS 环路

set -euo pipefail

DNS_PORT=1053    # mihomo DNS 监听端口
TABLE_NAME="qcg_proxy"

# 清理旧规则
nft delete table inet "$TABLE_NAME" 2>/dev/null || true

nft add table inet "$TABLE_NAME"

# ── 集合: AppVM 的 vif 接口 ──
nft add set inet "$TABLE_NAME" vif_interfaces '{ type ifname; }'
# 动态填充 vif 接口
for iface in /sys/class/net/vif*; do
    [ -d "$iface" ] && nft add element inet "$TABLE_NAME" vif_interfaces "{ $(basename $iface) }" 2>/dev/null || true
done

# ── 链: AppVM 流量劫持 ──
nft add chain inet "$TABLE_NAME" appvm_prerouting '{ type nat hook prerouting priority -100; policy accept; }'

# 只劫持来自 AppVM 接口的流量
nft add rule inet "$TABLE_NAME" appvm_prerouting iifname @vif_interfaces udp dport 53 \
    redirect to :$DNS_PORT
nft add rule inet "$TABLE_NAME" appvm_prerouting iifname @vif_interfaces tcp dport 53 \
    redirect to :$DNS_PORT

# ── 排除代理服务器 IP（避免环路） ──
# 用户需在 config.yaml 的 route-exclude-address 中配置
# 这里排除常见私有网段，代理服务器 IP 由 mihomo TUN 的 route-exclude-address 处理

echo "[✓] nftables 透明代理规则已加载"
echo "    DNS: AppVM:53 → localhost:${DNS_PORT}"
echo "    TCP/UDP: 由 mihomo TUN auto-route 处理"
NFTEOF
chmod +x "$NFT_SCRIPT"

# 加载 nftables 规则
bash "$NFT_SCRIPT"
info "nftables 规则已加载"

# qubes-firewall-user-script — VM 连接时自动重载 nftables
FW_SCRIPT="/rw/config/qubes-firewall-user-script"
cat > "$FW_SCRIPT" << 'FWEOF'
#!/bin/sh
# Auto-load nftables transparent proxy rules when VMs connect
/rw/config/clash/nftables-proxy.sh
FWEOF
chmod +x "$FW_SCRIPT"
info "qubes-firewall-user-script 已配置"

# systemd path unit — 监控新 vif 接口自动重载
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
info "VIF 监控服务已启动"

# rc.local — 持久化
RCLOCAL="/rw/config/rc.local"
# 先清理旧的 qcg 配置
if [ -f "$RCLOCAL" ]; then
    sed -i '/# === qubes-clash-gateway/,/# === end qubes-clash-gateway/d' "$RCLOCAL"
fi

cat >> "$RCLOCAL" << 'RCEOF'

# === qubes-clash-gateway ===
systemctl start mihomo 2>/dev/null || true
sleep 2
bash /rw/config/clash/nftables-proxy.sh 2>/dev/null || true
for vif in /sys/class/net/vif*; do
    [ -d "$vif" ] && ip link set "$(basename $vif)" up 2>/dev/null
done
# === end qubes-clash-gateway ===
RCEOF
chmod +x "$RCLOCAL"
info "rc.local 已配置（重启后自动恢复）"

# ==================== 6. 启动 ====================
step 6 "启动服务"
systemctl restart mihomo 2>/dev/null || true
sleep 2

if systemctl is-active --quiet mihomo; then
    info "mihomo 运行中"
else
    warn "mihomo 未启动（可能需要先配置节点）"
fi

# 完成
GATEWAY_IP=$(ip -4 addr show eth0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' || echo "?")
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║   qubes-clash-gateway 安装完成!                  ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "  配置:   $CONFIG_DIR/config.yaml"
echo "  DNS:    ${GATEWAY_IP}:${DNS_PORT} (fake-ip)"
echo "  API:    127.0.0.1:${API_PORT}"
echo ""
echo "  管理命令:"
echo "    clashctl /status       # 查看状态"
echo "    clashctl /mode rule    # 规则分流"
echo "    clashctl /mode global  # 全局代理"
echo "    clashctl /mode direct  # 直连"
echo "    clashctl /sub add <url>  # 添加订阅"
echo "    clashctl /node <name>  # 选择节点"
echo ""
echo "  下一步:"
echo "    1. 编辑配置添加节点: nano $CONFIG_DIR/config.yaml"
echo "    2. 重启: systemctl restart mihomo"
echo "    3. dom0: qvm-prefs <appvm> netvm $(hostname)"
echo "    4. 测试: curl -x socks5://127.0.0.1:7890 https://api.ipify.org"
echo ""
echo "  日志: journalctl -u mihomo -f"
echo "  卸载: bash $INSTALL_DIR/uninstall.sh"
echo ""
