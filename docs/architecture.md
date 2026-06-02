# System Architecture

This document describes the internal architecture of qubes-clash-gateway, covering traffic flow, DNS interception, the Kill Switch, Qubes VM isolation, and persistence.

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│  AppVM (e.g. work, personal)                                        │
│  Any application sends traffic → default route → NetVM gateway      │
└──────────────────────────┬──────────────────────────────────────────┘
                           │  vifX.Y interface (Qubes virtual NIC)
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│  NetVM (this machine)                                               │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  nftables (table: inet qcg_proxy)                             │  │
│  │                                                               │  │
│  │  appvm_prerouting (type nat, hook prerouting, prio -100):     │  │
│  │    DNS:  iif=vif* udp:53  → redirect :1053  (mihomo DNS)     │  │
│  │    DNS:  iif=vif* tcp:53  → redirect :1053  (mihomo DNS)     │  │
│  │    TCP:  iif=vif* tcp:*   → redirect :7892  (redir-port)     │  │
│  │           (excl. 22,1053,7890,7892,7893,9090,9091)            │  │
│  │    UDP:  iif=vif* udp:*   → redirect :7893  (tproxy-port)    │  │
│  │           (excl. 53,1053,7890,7892,7893)                      │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                           │                                         │
│                           ▼                                         │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  mihomo (TUN stack)                                           │  │
│  │                                                               │  │
│  │  :1053  DNS listener  ──→  fake-ip (198.18.0.0/16)           │  │
│  │  :7892  redir-port    ──→  TCP transparent proxy              │  │
│  │  :7893  tproxy-port   ──→  UDP transparent proxy              │  │
│  │  :7890  mixed-port    ──→  HTTP/SOCKS5 (Web UI, clashctl)    │  │
│  │  :9090  external-ctrl ──→  REST API                           │  │
│  │  :9091  Web UI        ──→  clashctl /web dashboard            │  │
│  │                                                               │  │
│  │  Routing rules: GeoIP/GeoSite → DIRECT or proxy node          │  │
│  │  TUN interface: mihomo's own outbound traffic                 │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                           │                                         │
│                           ▼                                         │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  nftables (table: ip qubes-firewall, chain: forward)          │  │
│  │  Kill Switch:                                                 │  │
│  │    non-vif inbound  → ACCEPT (NetVM's own outbound)           │  │
│  │    vif* → mihomo ports (tcp: 1053,7890,7892,7893,9090,9091)  │  │
│  │                              → ACCEPT                         │  │
│  │    vif* → mihomo ports (udp: 1053,7890,7892,7893) → ACCEPT   │  │
│  │    vif* → ICMP → DROP                                        │  │
│  │    vif* → everything else → DROP (policy drop)                │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                           │                                         │
│                           ▼                                         │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Upstream (physical NIC / sys-net)                            │  │
│  │  Proxy nodes, direct destinations, DNS upstream servers       │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

## DNS Hijack (Port 53 → 1053)

**Problem:** AppVMs send DNS queries to port 53 (standard DNS). mihomo needs to
intercept these to apply its enhanced DNS modes (fake-ip or redir-host).

**Solution:** nftables NAT `redirect` rules in the `appvm_prerouting` chain:

```
iifname @vif_interfaces udp dport 53  redirect to :1053
iifname @vif_interfaces tcp dport 53  redirect to :1053
```

Both UDP and TCP DNS are redirected to mihomo's DNS listener on port 1053.

**Why not mihomo's built-in dns-hijack?** mihomo's `auto-redirect` + `dns-hijack`
options create nftables rules that hijack ALL DNS traffic — including mihomo's own
outbound DNS queries going through the TUN interface. This creates a DNS loop.
By handling DNS hijack manually via nftables targeting only `vif*` interfaces,
mihomo's own DNS queries pass through unintercepted.

**Fake-IP mode (default):** mihomo returns addresses in the 198.18.0.0/16 range
for queried domains. When the application connects to this fake IP, mihomo
intercepts the TCP/UDP connection and knows the real domain from the mapping,
enabling domain-based routing rules.

## TCP Redirect (→ 7892)

**Rule:**
```
iifname @vif_interfaces tcp dport != { 22, 1053, 7890, 7892, 7893, 9090, 9091 }
    redirect to :7892
```

**Mechanism:** nftables NAT `redirect` rewrites the destination of TCP SYN packets
from AppVM vif interfaces to localhost:7892 (mihomo's `redir-port`). mihomo accepts
these connections and retrieves the original destination from the socket (SO_ORIGINAL_DST),
then applies routing rules.

**Excluded ports:**
- `22` — SSH to NetVM (avoid breaking admin access)
- `1053` — mihomo DNS listener (handled by DNS rules)
- `7890` — mihomo mixed-port (explicit proxy, avoid loop)
- `7892` — mihomo redir-port (avoid self-redirect loop)
- `7893` — mihomo tproxy-port (UDP, avoid loop)
- `9090` — mihomo external-controller API
- `9091` — clashctl Web UI

**Why redirect instead of tproxy for TCP?** TCP REDIRECT works at the NAT layer and
doesn't require special socket options. It's simpler and well-supported by mihomo's
redir-port.

## UDP Tproxy (→ 7893)

**Rule:**
```
iifname @vif_interfaces udp dport != { 53, 1053, 7890, 7892, 7893 }
    redirect to :7893
```

**Mechanism:** UDP traffic from AppVMs is redirected to mihomo's `tproxy-port` on
7893. For UDP, mihomo uses TPROXY (transparent proxy) which preserves the original
destination address via `recvmsg()` with `IP_ORIGDSTADDR`.

**Excluded ports:**
- `53` — DNS (handled by dedicated DNS redirect rules)
- `1053`, `7890`, `7892`, `7893` — mihomo's own ports (avoid loops)

**Note:** The `redirect to :7893` for UDP works because mihomo's tproxy-port
listens for UDP and can recover the original destination. The TUN stack handles
the actual forwarding upstream.

## Kill Switch

The Kill Switch ensures that if mihomo crashes or is stopped, AppVM traffic cannot
leak directly to the internet. It operates in the `qubes-firewall` forward chain.

### How It Works

```
qubes-firewall forward chain:
  1. iifname != "vif*" → ACCEPT
     (Allow NetVM's own outbound traffic through)

  2. iifname "vif*" tcp dport { 1053, 7890, 7892, 7893, 9090, 9091 } → ACCEPT
     (Allow AppVM → mihomo TCP ports)

  3. iifname "vif*" udp dport { 1053, 7890, 7892, 7893 } → ACCEPT
     (Allow AppVM → mihomo UDP ports)

  4. iifname "vif*" ip protocol icmp → DROP
     (Block ICMP — mihomo doesn't handle it, allowing = leak)

  5. [policy: DROP] — Everything else from vif* is dropped
```

### Behavior

- **mihomo running:** AppVM traffic hits nftables prerouting → redirected to
  mihomo ports → allowed through the forward chain → exits via upstream.
- **mihomo crashed:** AppVM traffic still gets redirected by prerouting rules, but
  since mihomo isn't listening, connections fail. The forward chain's policy-DROP
  prevents any direct internet access.
- **ICMP:** Always dropped. mihomo cannot proxy ICMP (ping), so allowing it would
  bypass the proxy entirely. `ping 8.8.8.8` from an AppVM will always fail.

### Testing the Kill Switch

```bash
# On NetVM
sudo systemctl stop mihomo

# On AppVM — everything should timeout
curl -s --max-time 8 https://api.ipify.org   # Expected: timeout
ping -c 1 8.8.8.8                              # Expected: 100% loss
```

## Qubes VM Isolation Model

### NetVM vs AppVM

Qubes OS uses a split-VM architecture:

| Component | Role | In This Project |
|-----------|------|-----------------|
| **sys-net** | Physical NIC driver, connects to hardware network | Upstream gateway |
| **sys-firewall** | Optional firewall VM | May sit between NetVM and sys-net |
| **NetVM** (this project) | Runs mihomo + nftables, provides gateway services | Transparent proxy gateway |
| **AppVM** | User-facing VMs (browser, work, etc.) | Traffic flows through NetVM |

### Network Topology

```
AppVM → (vifX.Y) → NetVM → (eth0/wlan0) → sys-net → Internet
```

When an AppVM is configured with `qvm-prefs <appvm> netvm <netvm-name>`, Qubes:

1. Creates a virtual NIC pair: `vifX.Y` on the NetVM, `eth0` inside the AppVM
2. Assigns IP addresses from the Qubes inter-VM network (typically APPVM_SUBNET)
3. Sets the AppVM's default gateway to the NetVM's vif-side IP
4. All AppVM traffic (except Qubes inter-VM on QUBES_INTERVM_CIDR) exits via the NetVM

### Why vif* Matching

nftables rules use `iifname @vif_interfaces` (a named set) to match traffic
coming from AppVMs. This is critical because:

- Only AppVM traffic (via vif interfaces) is intercepted
- The NetVM's own traffic (via eth0, wlan0, lo) is NOT intercepted
- mihomo's outbound traffic goes through the physical NIC, not through vif

### VIF Interface Lifecycle

When an AppVM boots, Qubes creates a new `vifX.Y` interface on the NetVM. The
nftables rules reference a named set `vif_interfaces` — only interfaces in this
set get transparent proxy interception.

Three mechanisms ensure new interfaces are added:

1. **Boot time** (`rc.local`): iterates `/sys/class/net/vif*` and adds all
   existing interfaces to the set
2. **udev rule** (`99-qcg-vif.rules`): triggers `auto-add-vif.sh` when a new
   `vif*` interface appears, adding it to the set immediately
3. **Manual reload**: `sudo bash /rw/config/clash/nftables-proxy.sh` rebuilds
   the entire table from scratch

The udev rule is recreated by `rc.local` on every boot (Qubes resets `/etc/`).

## Persistence Model

Qubes AppVMs use a template-based model where `/etc/` and most of the filesystem
is reset on every reboot. Only `/rw/config/` persists across restarts.

### Persistent Paths

| Path | Content | Purpose |
|------|---------|---------|
| `/rw/config/clash/` | All config files | mihomo config, subscriptions, rules, preferences |
| `/rw/config/clash/config.yaml` | Main mihomo config | Proxies, proxy-groups, DNS, rules, TUN settings |
| `/rw/config/clash/clashctl-subscriptions.json` | Subscription list | URL + last-update timestamps |
| `/rw/config/clash/clashctl-preferences.json` | User preferences | Mode, DNS preset, language |
| `/rw/config/clash/clashctl-custom-rules.yaml` | Custom routing rules | User-added rules injected before MATCH |
| `/rw/config/clash/rule-providers/` | Cached rule files | GeoSite/GeoIP YAML, auto-updated |
| `/rw/config/rc.local` | Boot script | Starts mihomo, loads nftables, recreates systemd service |
| `/rw/config/qubes-firewall-user-script` | VIF hook | Reloads nftables on VM connect |
| `/rw/config/sudoers.d/clashctl` | Sudoers rule | Passwordless sudo for clashctl operations |

### Non-Persistent Paths (Recreated at Boot)

| Path | How Recreated |
|------|---------------|
| `/usr/local/bin/mihomo` | Binary installed once to the template (or to `/rw/config/`) |
| `/etc/systemd/system/mihomo.service` | Recreated by `rc.local` on every boot |
| `/etc/udev/rules.d/99-qcg-vif.rules` | Recreated by `rc.local` on every boot |

### Boot Sequence

1. Qubes starts the NetVM from its template
2. `/rw/config/rc.local` executes:
   - Copies mihomo binary if needed
   - Creates the systemd service file
   - Starts mihomo via systemd
   - Runs `nftables-proxy.sh` to load transparent proxy + Kill Switch rules
3. When AppVMs boot, Qubes creates vif interfaces
4. `qcg-vif-monitor.path` detects new interfaces and reloads nftables
5. Traffic from AppVMs flows through the proxy

### Why rc.local?

Since `/etc/systemd/system/` is not persistent, the mihomo service file must be
recreated on every boot. `rc.local` is the simplest mechanism — it runs once at
boot time and can create files, start services, and load rules.
