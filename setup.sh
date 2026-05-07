#!/bin/bash
# qubes-clash-gateway 一键安装脚本
# 用法: curl -sSL https://raw.githubusercontent.com/iasds/qubes-clash-gateway/master/setup.sh | sudo bash
# 或: git clone ... && sudo bash setup.sh
set -euo pipefail

REPO_URL="https://github.com/iasds/qubes-clash-gateway.git"
INSTALL_DIR="/opt/qubes-clash-gateway"
GITHUB_REPO="MetaCubeX/mihomo"
MIHOMO_BIN="/usr/local/bin/mihomo"
CONFIG_DIR="/rw/config/clash"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[✗]${NC} $*"; exit 1; }
step()  { echo -e "\n${CYAN}[$1/$TOTAL_STEPS]${NC} $2"; }

TOTAL_STEPS=5

# ==================== 1. 环境检查 ====================
step 1 "检查环境"
[ "$(id -u)" -eq 0 ] || error "请用 sudo 运行此脚本"
command -v git >/dev/null || error "需要 git (apt install git)"
command -v curl >/dev/null || error "需要 curl (apt install curl)"
command -v python3 >/dev/null || error "需要 python3 (apt install python3)"
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
        # 如果 git clone 失败（需要认证），尝试下载 zip
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
    # 检查本地预下载
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
else
    info "配置已存在，跳过"
fi

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

# rc.local
RCLOCAL="/rw/config/rc.local"
if ! grep -q "qubes-clash-gateway" "$RCLOCAL" 2>/dev/null; then
    cat >> "$RCLOCAL" << 'RCEOF'

# === qubes-clash-gateway ===
systemctl start mihomo 2>/dev/null || true
for vif in /sys/class/net/vif*; do
    [ -d "$vif" ] && ip link set "$(basename $vif)" up 2>/dev/null
done
# === end qubes-clash-gateway ===
RCEOF
    chmod +x "$RCLOCAL"
    info "rc.local 已配置"
else
    info "rc.local 已包含配置"
fi

# ==================== 5. 启动 ====================
step 5 "启动服务"
systemctl start mihomo 2>/dev/null || true
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
echo "  配置:  $CONFIG_DIR/config.yaml"
echo "  代理:  $GATEWAY_IP:7890 (HTTP/SOCKS5)"
echo "  DNS:   $GATEWAY_IP:1053 (fake-ip)"
echo ""
echo "  下一步:"
echo "  1. 编辑配置添加节点: nano $CONFIG_DIR/config.yaml"
echo "  2. 重启: systemctl restart mihomo"
echo "  3. 测试: bash $INSTALL_DIR/scripts/test.sh"
echo "  4. dom0: qvm-prefs <appvm> netvm $(hostname)"
echo ""
echo "  管理:  journalctl -u mihomo -f"
echo "  卸载:  bash $INSTALL_DIR/uninstall.sh"
echo ""
