#!/bin/bash
# qubes-clash-gateway 安装脚本（基础版）
# 提示: 推荐使用 setup.sh 进行完整安装（含 nftables、clashctl、sudoers）
# 本脚本仅做基础安装（mihomo + systemd + rc.local）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_DIR="/rw/config/clash"
MIHOMO_BIN="/usr/local/bin/mihomo"
SERVICE_NAME="mihomo"
GITHUB_REPO="MetaCubeX/mihomo"

# 颜色
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[✗]${NC} $*"; exit 1; }

# ==================== 检查环境 ====================
check_env() {
    [ "$(id -u)" -eq 0 ] || error "请用 sudo 运行"
    command -v python3 >/dev/null || error "需要 python3"
    info "环境检查通过"
}

# ==================== 下载 mihomo ====================
download_mihomo() {
    if [ -f "$MIHOMO_BIN" ]; then
        info "mihomo 已存在: $MIHOMO_BIN"
        "$MIHOMO_BIN" -v 2>/dev/null || warn "版本检查失败，继续安装"
        return 0
    fi

    # 检查本地预下载
    for candidate in "$SCRIPT_DIR/mihomo" "$SCRIPT_DIR/mihomo.gz" "/tmp/mihomo" "/tmp/mihomo.gz"; do
        if [ -f "$candidate" ]; then
            if [[ "$candidate" == *.gz ]]; then
                info "解压本地文件: $candidate"
                gunzip -c "$candidate" > "$MIHOMO_BIN"
            else
                info "复制本地文件: $candidate"
                cp "$candidate" "$MIHOMO_BIN"
            fi
            chmod +x "$MIHOMO_BIN"
            info "mihomo 安装完成"
            return 0
        fi
    done

    # 从 GitHub 下载
    info "从 GitHub 下载 mihomo..."
    local api_url="https://api.github.com/repos/${GITHUB_REPO}/releases"
    local download_url=""

    # 尝试获取最新 release 的 linux-amd64 资产
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
        info "下载: $download_url"
        if curl -fL --connect-timeout 15 -o /tmp/mihomo.gz "$download_url"; then
            gunzip -c /tmp/mihomo.gz > "$MIHOMO_BIN"
            chmod +x "$MIHOMO_BIN"
            rm -f /tmp/mihomo.gz
            info "mihomo 下载安装完成"
            return 0
        fi
        warn "GitHub 下载失败"
    else
        warn "无法获取下载链接（API 限流或网络问题）"
    fi

    # 所有方式失败
    echo ""
    error "无法下载 mihomo。请手动操作：
  1. 从其他机器下载: https://github.com/MetaCubeX/mihomo/releases
  2. 选择 linux-amd64 的 .gz 文件
  3. 传输到此机器: scp mihomo.gz $(hostname):/tmp/
  4. 重新运行此脚本"
}

# ==================== 创建配置目录 ====================
setup_config() {
    mkdir -p "$CONFIG_DIR"

    if [ ! -f "$CONFIG_DIR/config.yaml" ]; then
        info "复制默认配置到 $CONFIG_DIR/config.yaml"
        cp "$SCRIPT_DIR/config/config.yaml" "$CONFIG_DIR/config.yaml"
    else
        info "配置已存在，跳过（$CONFIG_DIR/config.yaml）"
    fi

    # 确保非 root 用户可读写
    chown -R "$(logname 2>/dev/null || echo user):$(logname 2>/dev/null || echo user)" "$CONFIG_DIR" 2>/dev/null || true
}

# ==================== 创建 systemd service ====================
setup_service() {
    local service_file="/etc/systemd/system/${SERVICE_NAME}.service"

    info "创建 systemd service"
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
    info "systemd service 已创建并启用"
}

# ==================== 设置 Qubes NetVM rc.local ====================
setup_rclocal() {
    local rclocal="/rw/config/rc.local"

    # 备份已有 rc.local
    if [ -f "$rclocal" ] && [ -s "$rclocal" ]; then
        cp "$rclocal" "${rclocal}.bak.$(date +%Y%m%d%H%M%S)"
        info "已备份 rc.local"
    fi

    # 检查是否已包含我们的配置
    if [ -f "$rclocal" ] && grep -q "qubes-clash-gateway" "$rclocal" 2>/dev/null; then
        info "rc.local 已包含 clash 配置，跳过"
        return 0
    fi

    info "追加 clash 启动配置到 rc.local"
    cat >> "$rclocal" << 'RCEOF'

# === qubes-clash-gateway ===
# 启动 mihomo 透明代理
systemctl start mihomo 2>/dev/null || true

# 确保 vif 接口 up
for vif in /sys/class/net/vif*; do
    [ -d "$vif" ] && ip link set "$(basename $vif)" up 2>/dev/null
done
# === end qubes-clash-gateway ===
RCEOF

    chmod +x "$rclocal"
    info "rc.local 配置完成"
}

# ==================== 启动服务 ====================
start_service() {
    info "启动 mihomo..."
    systemctl start "$SERVICE_NAME"
    sleep 2

    if systemctl is-active --quiet "$SERVICE_NAME"; then
        info "mihomo 运行中"
        "$MIHOMO_BIN" -v 2>/dev/null && true
    else
        warn "mihomo 启动失败，检查日志: journalctl -u $SERVICE_NAME -n 20"
        warn "可能需要先配置订阅节点到 $CONFIG_DIR/config.yaml"
    fi
}

# ==================== 完成 ====================
print_summary() {
    local ip
    ip=$(ip -4 addr show eth0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' || echo "未知")
    echo ""
    echo "=========================================="
    echo "  qubes-clash-gateway 安装完成"
    echo "=========================================="
    echo ""
    echo "  配置文件: $CONFIG_DIR/config.yaml"
    echo "  代理端口: 7890 (HTTP/SOCKS5)"
    echo "  DNS 端口: 1053 (fake-ip)"
    echo "  网关地址: $ip"
    echo ""
    echo "  下一步:"
    echo "  1. 添加订阅节点: 编辑 $CONFIG_DIR/config.yaml"
    echo "  2. 重启服务: sudo systemctl restart mihomo"
    echo "  3. 测试: curl -x socks5h://127.0.0.1:7890 https://www.google.com"
    echo "  4. 在 dom0 设置 AppVM: qvm-prefs <appvm> netvm $(hostname)"
    echo ""
    echo "  管理:"
    echo "  - 查看日志: journalctl -u mihomo -f"
    echo "  - 重启: sudo systemctl restart mihomo"
    echo "  - 卸载: sudo bash $SCRIPT_DIR/uninstall.sh"
    echo ""
}

# ==================== 主流程 ====================
main() {
    echo ""
    echo "╔══════════════════════════════════════════╗"
    echo "║   qubes-clash-gateway 安装程序           ║"
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
