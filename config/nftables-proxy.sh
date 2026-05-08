#!/bin/bash
# qubes-clash-gateway nftables 透明代理规则
# 核心思路: 禁用 mihomo 的 dns-hijack/auto-redirect，手动用 nftables 劫持 AppVM 流量
# 这样 mihomo 自己的 DNS 查询不会被劫持回 TUN，彻底解决 DNS 环路

set -euo pipefail
export PATH=$PATH:/usr/sbin

DNS_PORT=1053      # mihomo DNS 监听端口
REDIR_PORT=7892    # mihomo redir-port (TCP 透明代理)
TPROXY_PORT=7893   # mihomo tproxy-port (UDP 透明代理)
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

# DNS 劫持: AppVM:53 → mihomo DNS
nft add rule inet "$TABLE_NAME" appvm_prerouting iifname @vif_interfaces udp dport 53 redirect to :$DNS_PORT
nft add rule inet "$TABLE_NAME" appvm_prerouting iifname @vif_interfaces tcp dport 53 redirect to :$DNS_PORT

# TCP 透明代理: AppVM TCP → mihomo redir-port (排除代理相关端口避免环路)
nft add rule inet "$TABLE_NAME" appvm_prerouting iifname @vif_interfaces tcp dport != { 22, 1053, 7890, 7892, 7893, 9090, 9091 } redirect to :$REDIR_PORT

# UDP 透明代理: AppVM UDP → mihomo tproxy-port (排除 DNS 和代理端口)
nft add rule inet "$TABLE_NAME" appvm_prerouting iifname @vif_interfaces udp dport != { 53, 1053, 7890, 7892, 7893 } redirect to :$TPROXY_PORT

# ── 允许 AppVM 访问 mihomo 端口 (Qubes input chain) ──
nft add rule ip qubes custom-input iifgroup 2 tcp dport { 1053, 7890, 7892, 7893, 9090, 9091 } accept 2>/dev/null || true
nft add rule ip qubes custom-input iifgroup 2 udp dport { 1053, 7890, 7892, 7893 } accept 2>/dev/null || true

# ── 允许 AppVM 流量转发 (Qubes forward chain) ──
nft add rule ip qubes custom-forward iifgroup 2 oifgroup 1 accept 2>/dev/null || true
nft insert rule ip qubes-firewall forward iifname "vif*" accept 2>/dev/null || true

echo "[✓] nftables 透明代理规则已加载"
echo "    DNS: AppVM:53 → localhost:${DNS_PORT}"
echo "    TCP: AppVM:* → localhost:${REDIR_PORT} (redir-port)"
echo "    UDP: AppVM:* → localhost:${TPROXY_PORT} (tproxy-port)"
