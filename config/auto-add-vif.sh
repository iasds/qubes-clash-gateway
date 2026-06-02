#!/bin/bash
# Auto-add new vif interface to nftables set when VM connects
export PATH=$PATH:/usr/sbin
IFACE="$1"
[ -z "$IFACE" ] && exit 0
[[ ! "$IFACE" =~ ^vif ]] && exit 0

# Wait for interface to be ready
sleep 1

# Add to nftables set
nft add element inet qcg_proxy vif_interfaces "{ $IFACE }" 2>/dev/null

# Also ensure qubes-firewall rules exist (idempotent inserts)
nft insert rule ip qubes-firewall forward iifname "vif*" tcp dport { 1053, 7890, 7892, 7893, 9090, 9091 } accept 2>/dev/null || true
nft insert rule ip qubes-firewall forward iifname "vif*" udp dport { 1053, 7890, 7892, 7893 } accept 2>/dev/null || true
nft insert rule ip qubes-firewall forward iifname "vif*" ip protocol icmp drop 2>/dev/null || true

logger -t qcg "Added $IFACE to nftables vif_interfaces set"
