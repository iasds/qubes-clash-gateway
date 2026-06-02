# nftables Rules Reference

This document is a line-by-line reference for every nftables rule defined in
`config/nftables-proxy.sh`. Each rule includes its chain, purpose, rationale,
and security implications.

## Overview

The script creates two logical sets of rules:

1. **`inet qcg_proxy` table** — Transparent proxy rules (DNS, TCP, UDP hijack)
2. **`ip qubes-firewall` forward chain** — Kill Switch rules

Plus a small addition to the existing `ip qubes` table for input acceptance.

---

## 1. Cleanup: Delete Old Table

```bash
nft delete table inet "$TABLE_NAME" 2>/dev/null || true
```

| Attribute | Value |
|-----------|-------|
| Chain | N/A (table-level operation) |
| Purpose | Remove the entire `qcg_proxy` table if it already exists |
| Why | Ensures idempotency — the script can be re-run safely without creating duplicate rules |
| Security | None. Cleanup only. |

---

## 2. Create Table

```bash
nft add table inet "$TABLE_NAME"
```

| Attribute | Value |
|-----------|-------|
| Chain | N/A (creates `inet qcg_proxy`) |
| Purpose | Create the top-level nftables table for all proxy rules |
| Why | Isolates proxy rules from Qubes system rules; easy to delete/recreate |
| Security | The `inet` family handles both IPv4 and IPv6 traffic |

---

## 3. VIF Interfaces Set

```bash
nft add set inet "$TABLE_NAME" vif_interfaces '{ type ifname; }'
```

| Attribute | Value |
|-----------|-------|
| Chain | N/A (named set) |
| Purpose | Create a named set of interface names for matching AppVM vif interfaces |
| Why | Using a set instead of wildcard `vif*` is more precise and allows dynamic updates |
| Security | Only traffic from interfaces in this set gets intercepted — NetVM's own traffic is untouched |

### Populate the Set

```bash
for iface in /sys/class/net/vif*; do
    [ -d "$iface" ] && nft add element inet "$TABLE_NAME" vif_interfaces "{ $(basename $iface) }" 2>/dev/null || true
done
```

| Attribute | Value |
|-----------|-------|
| Purpose | Dynamically discover all `vif*` interfaces and add them to the set |
| Why | Qubes creates vif interfaces dynamically when AppVMs start; this captures all current ones |
| Security | If no vif interfaces exist (no AppVMs running), the set is empty and no traffic is intercepted |

---

## 4. AppVM Prerouting Chain

```bash
nft add chain inet "$TABLE_NAME" appvm_prerouting '{ type nat hook prerouting priority -100; policy accept; }'
```

| Attribute | Value |
|-----------|-------|
| Chain | `inet qcg_proxy appvm_prerouting` |
| Hook | `prerouting` (before routing decision) |
| Type | `nat` (required for REDIRECT) |
| Priority | `-100` (runs early, before other prerouting hooks) |
| Policy | `accept` (non-matching traffic passes through unchanged) |
| Purpose | Intercept outbound traffic from AppVMs before it hits the routing table |
| Why | `prerouting` is the only hook where NAT `redirect` works — it rewrites the destination before routing decides the next hop |
| Security | Priority -100 ensures rules run before any other prerouting processing |

---

## 5. DNS Rules

### UDP DNS

```bash
nft add rule inet "$TABLE_NAME" appvm_prerouting \
    iifname @vif_interfaces udp dport 53 redirect to :$DNS_PORT
```

| Attribute | Value |
|-----------|-------|
| Chain | `appvm_prerouting` |
| Match | Input interface in `vif_interfaces` AND UDP destination port 53 |
| Action | `redirect to :1053` — rewrite destination to localhost:1053 |
| Purpose | Hijack AppVM DNS queries (UDP) and route them to mihomo's DNS listener |
| Why | mihomo's DNS engine (fake-ip/redir-host mode) handles DNS resolution with anti-pollution features |
| Security | Only vif traffic is intercepted. mihomo's own outbound DNS (via physical NIC) is NOT intercepted, preventing DNS loops |

### TCP DNS

```bash
nft add rule inet "$TABLE_NAME" appvm_prerouting \
    iifname @vif_interfaces tcp dport 53 redirect to :$DNS_PORT
```

| Attribute | Value |
|-----------|-------|
| Chain | `appvm_prerouting` |
| Match | Input interface in `vif_interfaces` AND TCP destination port 53 |
| Action | `redirect to :1053` |
| Purpose | Hijack AppVM DNS-over-TCP queries and route to mihomo |
| Why | Some resolvers fall back to TCP for large responses; DNS-over-TLS/HTTPS also uses TCP |
| Security | Same as UDP DNS rule — only vif traffic matched |

---

## 6. TCP Transparent Proxy Rule

```bash
nft add rule inet "$TABLE_NAME" appvm_prerouting \
    iifname @vif_interfaces tcp dport != { 22, 1053, 7890, 7892, 7893, 9090, 9091 } \
    redirect to :$REDIR_PORT
```

| Attribute | Value |
|-----------|-------|
| Chain | `appvm_prerouting` |
| Match | Input interface in `vif_interfaces` AND TCP AND destination port NOT in exclusion set |
| Action | `redirect to :7892` — rewrite destination to mihomo's redir-port |
| Purpose | Transparently proxy all TCP traffic from AppVMs through mihomo |
| Why | mihomo's redir-port uses `SO_ORIGINAL_DST` to recover the real destination, then applies routing rules |

**Excluded ports and reasons:**

| Port | Service | Why Excluded |
|------|---------|--------------|
| 22 | SSH to NetVM | Without this, SSH to the NetVM itself would be redirected to mihomo and fail |
| 1053 | mihomo DNS | Already handled by DNS rules; redirecting again would create a loop |
| 7890 | mihomo mixed-port | Explicit proxy port; redirecting would create a self-loop |
| 7892 | mihomo redir-port | Self-redirect would create an infinite loop |
| 7893 | mihomo tproxy-port | UDP port, but included for safety |
| 9090 | mihomo external-controller API | Management API must remain directly accessible |
| 9091 | clashctl Web UI | Dashboard must remain directly accessible |

**Security:** If a port is missing from the exclusion list, traffic to that port
on the NetVM would be silently redirected to mihomo, potentially breaking services.

---

## 7. UDP Transparent Proxy Rule

```bash
nft add rule inet "$TABLE_NAME" appvm_prerouting \
    iifname @vif_interfaces udp dport != { 53, 1053, 7890, 7892, 7893 } \
    redirect to :$TPROXY_PORT
```

| Attribute | Value |
|-----------|-------|
| Chain | `appvm_prerouting` |
| Match | Input interface in `vif_interfaces` AND UDP AND destination port NOT in exclusion set |
| Action | `redirect to :7893` — rewrite destination to mihomo's tproxy-port |
| Purpose | Transparently proxy all UDP traffic (except DNS) through mihomo |
| Why | UDP traffic (e.g., QUIC, WebRTC, gaming) needs proxy support for complete coverage |

**Excluded ports and reasons:**

| Port | Service | Why Excluded |
|------|---------|--------------|
| 53 | DNS | Handled by dedicated DNS redirect rules |
| 1053 | mihomo DNS | Avoid loop |
| 7890 | mihomo mixed-port | Avoid loop |
| 7892 | mihomo redir-port | Avoid loop |
| 7893 | mihomo tproxy-port | Self-redirect loop |

**Security:** DNS port 53 is excluded here because it has its own dedicated rules.
If it weren't excluded, DNS queries would hit the tproxy rule and potentially be
handled incorrectly (mihomo's tproxy-port is for general UDP, not DNS).

---

## 8. Qubes Custom-Input Rules

```bash
nft add rule ip qubes custom-input iifgroup 2 tcp dport { 1053, 7890, 7892, 7893, 9090, 9091 } accept 2>/dev/null || true
nft add rule ip qubes custom-input iifgroup 2 udp dport { 1053, 7890, 7892, 7893 } accept 2>/dev/null || true
```

| Attribute | Value |
|-----------|-------|
| Chain | `ip qubes custom-input` (Qubes-managed chain) |
| Match | Input interface group 2 (VM interfaces) AND destination port in mihomo port set |
| Action | `accept` |
| Purpose | Allow AppVM traffic to reach mihomo's listening ports on the NetVM |
| Why | Qubes' default firewall policy may block inbound connections from VMs. These rules explicitly permit traffic to mihomo's ports |
| Security | Only mihomo-related ports are opened. Other NetVM services remain inaccessible from AppVMs |

**Interface group 2:** In Qubes, `iifgroup 2` matches all interfaces connected to
VMs (vif* interfaces). This is the Qubes-standard way to match VM-originating traffic.

**Port coverage:**
- TCP: 1053 (DNS), 7890 (mixed), 7892 (redir), 7893 (tproxy), 9090 (API), 9091 (web)
- UDP: 1053 (DNS), 7890 (mixed), 7892 (redir), 7893 (tproxy)

**Note:** The `2>/dev/null || true` suppresses errors if the `qubes` table or
`custom-input` chain doesn't exist (e.g., on non-Qubes systems).

---

## 9. Kill Switch Rules (qubes-firewall forward chain)

These rules are added to the Qubes-managed `ip qubes-firewall forward` chain.
The script first cleans up any previously-added QCG rules to ensure idempotency.

### 9a. Cleanup Old Rules

```bash
for handle in $(nft -a list chain ip qubes-firewall forward 2>/dev/null \
    | grep -E "vif.*accept|vif.*icmp.*drop|iifname != \"vif\".*accept" \
    | awk '{print $NF}'); do
    nft delete rule ip qubes-firewall forward handle "$handle" 2>/dev/null || true
done
```

| Attribute | Value |
|-----------|-------|
| Chain | `ip qubes-firewall forward` |
| Purpose | Remove previously-added QCG Kill Switch rules by matching their patterns |
| Why | Prevents rule duplication on re-run; the script is idempotent |
| Security | Only rules matching QCG-specific patterns (vif accept, icmp drop) are removed |

### 9b. Allow NetVM's Own Outbound

```bash
nft insert rule ip qubes-firewall forward iifname != "vif*" accept 2>/dev/null || true
```

| Attribute | Value |
|-----------|-------|
| Chain | `ip qubes-firewall forward` |
| Match | Input interface is NOT a vif interface |
| Action | `accept` |
| Purpose | Allow the NetVM's own outbound traffic to pass through without restrictions |
| Why | Without this, the NetVM's own connections (e.g., upstream DNS, subscription fetches) would be blocked by the policy-drop |
| Security | This only matches non-vif interfaces (eth0, wlan0, lo, tun*), not AppVM traffic |

### 9c. Allow TCP to mihomo Ports

```bash
nft insert rule ip qubes-firewall forward iifname "vif*" tcp dport { 1053, 7890, 7892, 7893, 9090, 9091 } accept 2>/dev/null || true
```

| Attribute | Value |
|-----------|-------|
| Chain | `ip qubes-firewall forward` |
| Match | Input interface is `vif*` AND TCP destination port is a mihomo port |
| Action | `accept` |
| Purpose | Allow AppVM TCP traffic to reach mihomo's listening ports |
| Why | The prerouting chain redirects traffic to these ports, but the forward chain must also allow it through |
| Security | Only mihomo management ports are allowed. All other TCP destinations from vif* are dropped by policy |

### 9d. Allow UDP to mihomo Ports

```bash
nft insert rule ip qubes-firewall forward iifname "vif*" udp dport { 1053, 7890, 7892, 7893 } accept 2>/dev/null || true
```

| Attribute | Value |
|-----------|-------|
| Chain | `ip qubes-firewall forward` |
| Match | Input interface is `vif*` AND UDP destination port is a mihomo port |
| Action | `accept` |
| Purpose | Allow AppVM UDP traffic to reach mihomo's listening ports |
| Why | Same rationale as TCP — the forward chain must permit traffic that was redirected by prerouting |
| Security | Only the 4 mihomo UDP ports are allowed |

### 9e. Block ICMP

```bash
nft insert rule ip qubes-firewall forward iifname "vif*" ip protocol icmp drop 2>/dev/null || true
```

| Attribute | Value |
|-----------|-------|
| Chain | `ip qubes-firewall forward` |
| Match | Input interface is `vif*` AND IP protocol is ICMP |
| Action | `drop` |
| Purpose | Block all ICMP traffic from AppVMs |
| Why | mihomo cannot proxy ICMP packets. If ICMP were allowed, `ping` and `traceroute` would bypass the proxy entirely, leaking the real IP and network path |
| Security | **Critical.** Without this rule, ICMP traffic would bypass the proxy. `ping 8.8.8.8` from an AppVM would show the real network path |

### 9f. Implicit Policy Drop

The `qubes-firewall` forward chain has a default policy of `drop`. After the
explicit `accept` rules above, any remaining vif* traffic that doesn't match
(most importantly, traffic to non-mihomo ports) is silently dropped.

**This is the core Kill Switch:** if mihomo crashes:
1. Prerouting rules still redirect traffic to mihomo's ports
2. But nothing is listening on those ports → connections fail
3. Traffic to non-mihomo ports is blocked by the forward chain's policy-drop
4. No fallback to direct internet access is possible

---

## Complete Rule Summary

```
┌─────────────────────────────────────────────────────────────────────┐
│ inet qcg_proxy                                                      │
│                                                                     │
│ set vif_interfaces { vif1.0, vif2.0, ... }                         │
│                                                                     │
│ chain appvm_prerouting (nat hook prerouting prio -100)              │
│   ┌─┬────────────────────────────────────────────────────────────┐  │
│   │1│ iif=vif* udp:53       → redirect :1053  (DNS)             │  │
│   │2│ iif=vif* tcp:53       → redirect :1053  (DNS)             │  │
│   │3│ iif=vif* tcp:* !excl  → redirect :7892  (TCP proxy)       │  │
│   │4│ iif=vif* udp:* !excl  → redirect :7893  (UDP proxy)       │  │
│   └─┴────────────────────────────────────────────────────────────┘  │
│                                                                     │
│ ip qubes custom-input                                               │
│   ┌─┬────────────────────────────────────────────────────────────┐  │
│   │5│ iifgroup=2 tcp mihomo-ports → accept                      │  │
│   │6│ iifgroup=2 udp mihomo-ports → accept                      │  │
│   └─┴────────────────────────────────────────────────────────────┘  │
│                                                                     │
│ ip qubes-firewall forward                                           │
│   ┌─┬────────────────────────────────────────────────────────────┐  │
│   │7│ iif!=vif*             → accept  (NetVM own traffic)       │  │
│   │8│ iif=vif* tcp mihomo   → accept                            │  │
│   │9│ iif=vif* udp mihomo   → accept                            │  │
│   │A│ iif=vif* icmp         → drop    (Kill Switch)             │  │
│   │B│ [policy: drop]        → drop    (Kill Switch)             │  │
│   └─┴────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

## Order of Operations

For a typical TCP connection from an AppVM (e.g., `curl https://example.com`):

1. Packet arrives on `vif1.0` with dst=`example.com:443`
2. **Prerouting (rule 3):** Matched — dst rewritten to `127.0.0.1:7892`
3. Routing decision: packet is now destined for localhost → goes through forward chain
4. **Forward (rule 8):** Matched (tcp dport 7892 is in mihomo ports) → `accept`
5. Packet delivered to mihomo on port 7892
6. mihomo reads `SO_ORIGINAL_DST` → knows real destination is `example.com:443`
7. mihomo applies routing rules → connects via proxy or DIRECT
8. Response flows back through the reverse path

For DNS:

1. AppVM sends UDP to `8.8.8.8:53`
2. **Prerouting (rule 1):** Matched — dst rewritten to `127.0.0.1:1053`
3. Packet delivered to mihomo DNS listener
4. mihomo resolves using fake-ip → returns `198.18.x.x`
5. AppVM connects to `198.18.x.x:443` → intercepted by prerouting rule 3 → proxied
