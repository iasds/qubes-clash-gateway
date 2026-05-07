#!/bin/bash
# qubes-clash-gateway 连通性测试脚本
# 在 NetVM 上运行：测试代理是否正常工作
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
pass() { echo -e "  ${GREEN}✓${NC} $*"; }
fail() { echo -e "  ${RED}✗${NC} $*"; }
warn() { echo -e "  ${YELLOW}!${NC} $*"; }

PROXY="socks5h://127.0.0.1:7890"
TIMEOUT=10

echo ""
echo "=== qubes-clash-gateway 连通性测试 ==="
echo ""

# 1. 检查 mihomo 进程
echo "1. 服务状态"
if systemctl is-active --quiet mihomo 2>/dev/null; then
    pass "mihomo 服务运行中"
else
    fail "mihomo 服务未运行"
    echo "     尝试: sudo systemctl start mihomo"
fi

# 2. 检查端口监听
echo ""
echo "2. 端口监听"
if ss -tlnp | grep -q ":7890"; then
    pass "代理端口 7890 已监听"
else
    fail "代理端口 7890 未监听"
fi
if ss -ulnp | grep -q ":1053"; then
    pass "DNS 端口 1053 已监听"
else
    fail "DNS 端口 1053 未监听"
fi

# 3. TUN 接口
echo ""
echo "3. TUN 接口"
if ip link show mihomo 2>/dev/null || ip link show tun0 2>/dev/null; then
    pass "TUN 接口存在"
else
    warn "未检测到 TUN 接口（可能使用其他名称）"
fi

# 4. 通过代理访问国内站点
echo ""
echo "4. 国内直连测试"
code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout $TIMEOUT -x "$PROXY" "https://www.baidu.com" 2>/dev/null || echo "000")
if [ "$code" = "200" ] || [ "$code" = "302" ]; then
    pass "baidu.com → HTTP $code"
else
    fail "baidu.com → HTTP $code"
fi

# 5. 通过代理访问国外站点
echo ""
echo "5. 代理转发测试"
code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout $TIMEOUT -x "$PROXY" "https://www.google.com" 2>/dev/null || echo "000")
if [ "$code" = "200" ] || [ "$code" = "302" ]; then
    pass "google.com → HTTP $code"
else
    fail "google.com → HTTP $code"
fi

# 6. 出口 IP
echo ""
echo "6. 出口 IP"
ip=$(curl -s --connect-timeout $TIMEOUT -x "$PROXY" "https://api.ipify.org" 2>/dev/null || echo "获取失败")
if [ "$ip" != "获取失败" ] && [ -n "$ip" ]; then
    pass "出口 IP: $ip"
else
    fail "无法获取出口 IP"
fi

# 7. DNS 解析（fake-ip 测试）
echo ""
echo "7. DNS 解析"
dns_result=$(dig +short @127.0.0.1 -p 1053 google.com 2>/dev/null || echo "")
if [ -n "$dns_result" ]; then
    pass "DNS 解析: google.com → $dns_result"
    if echo "$dns_result" | grep -q "^198\.18\."; then
        pass "fake-ip 模式生效 (198.18.x.x)"
    else
        warn "非 fake-ip 地址，可能使用 redir-host 模式"
    fi
else
    fail "DNS 解析失败"
fi

echo ""
echo "=== 测试完成 ==="
echo ""
echo "如果 AppVM 无法上网，请在 dom0 确认:"
echo "  qvm-prefs <appvm-name> netvm $(hostname)"
