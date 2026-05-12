#!/bin/bash
# qubes-clash-gateway nftables transparent proxy rules
# Core idea: Disable mihomo's dns-hijack/auto-redirect, manually use nftables to hijack AppVM traffic
# This way mihomo's own DNS queries won't be hijacked back to TUN, fully resolving DNS loops

set -euo pipefail
export PATH=$PATH:/usr/sbin

DNS_PORT=1053      # mihomo DNS listen port
REDIR_PORT=7892    # mihomo redir-port (TCP transparent proxy)
TPROXY_PORT=7893   # mihomo tproxy-port (UDP transparent proxy)
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

# DNS hijack: AppVM:53 → mihomo DNS
nft add rule inet "$TABLE_NAME" appvm_prerouting iifname @vif_interfaces udp dport 53 redirect to :$DNS_PORT
nft add rule inet "$TABLE_NAME" appvm_prerouting iifname @vif_interfaces tcp dport 53 redirect to :$DNS_PORT

# TCP transparent proxy: AppVM TCP → mihomo redir-port (exclude proxy-related ports to avoid loops)
nft add rule inet "$TABLE_NAME" appvm_prerouting iifname @vif_interfaces tcp dport != { 22, 1053, 7890, 7892, 7893, 9090, 9091 } redirect to :$REDIR_PORT

# UDP transparent proxy: AppVM UDP → mihomo tproxy-port (exclude DNS and proxy ports)
nft add rule inet "$TABLE_NAME" appvm_prerouting iifname @vif_interfaces udp dport != { 53, 1053, 7890, 7892, 7893 } redirect to :$TPROXY_PORT

# ── Allow AppVM to access mihomo ports (Qubes input chain) ──
nft add rule ip qubes custom-input iifgroup 2 tcp dport { 1053, 7890, 7892, 7893, 9090, 9091 } accept 2>/dev/null || true
nft add rule ip qubes custom-input iifgroup 2 udp dport { 1053, 7890, 7892, 7893 } accept 2>/dev/null || true

# ── Kill Switch: AppVM forwarding control (Qubes forward chain) ──
# Remove old blanket "vif* accept" rules if present
for handle in $(nft -a list chain ip qubes-firewall forward 2>/dev/null | grep "vif.*accept" | awk '{print $NF}'); do
    nft delete rule ip qubes-firewall forward handle "$handle" 2>/dev/null || true
done

# Allow sys-proxy own outbound (non-vif interfaces)
nft insert rule ip qubes-firewall forward iifname != "vif*" accept 2>/dev/null || true
# Only allow AppVM traffic to mihomo ports — everything else dropped by policy drop
nft insert rule ip qubes-firewall forward iifname "vif*" tcp dport { 1053, 7890, 7892, 7893, 9090, 9091 } accept 2>/dev/null || true
nft insert rule ip qubes-firewall forward iifname "vif*" udp dport { 1053, 7890, 7892, 7893 } accept 2>/dev/null || true
# Block ICMP (Clash doesn't handle ICMP — allowing it = leak)
nft insert rule ip qubes-firewall forward iifname "vif*" ip protocol icmp drop 2>/dev/null || true

echo "[✓] nftables transparent proxy + Kill Switch loaded"
echo "    DNS: AppVM:53 → localhost:${DNS_PORT}"
echo "    TCP: AppVM:* → localhost:${REDIR_PORT} (redir-port)"
echo "    UDP: AppVM:* → localhost:${TPROXY_PORT} (tproxy-port)"
echo "    Kill Switch: ICMP blocked, only mihomo ports forwarded"
