# Qubes Clash Gateway

A learning project exploring **Qubes OS networking architecture** — building a transparent traffic gateway using [mihomo](https://github.com/MetaCubeX/mihomo), nftables, and systemd on a NetVM.

> **Educational purpose only.** This project is designed to study OS-level networking concepts including transparent proxying, DNS interception, traffic routing, nftables rule design, and Qubes VM isolation architecture. Users are responsible for complying with all applicable laws and regulations in their jurisdiction.

## Learning Objectives

- **Qubes OS networking** — Understand how NetVM, AppVM, and vif interfaces interact
- **Transparent proxy architecture** — Learn nftables REDIRECT/TPROXY, DNS hijacking, and traffic interception
- **DNS engineering** — Explore fake-ip mode, DNS pollution prevention, and split DNS resolution
- **Service management** — systemd units, rc.local boot scripts, and Qubes persistent storage
- **CLI tooling** — Build a terminal controller with Python, REST API integration, and Web UI

## Architecture

```
AppVM → vif* interface → nftables redirect → mihomo (TUN stack)
                                           ├→ DNS :53 → :1053 (fake-ip)
                                           ├→ TCP  → :7892 (redir-port)
                                           └→ UDP  → :7893 (tproxy-port)

mihomo routing rules:
  ├→ GeoIP/GeoSite matching → direct or proxy
  └→ Subscription-based node selection
```

Key design decisions (see `config/config.yaml`):
- **Disable** `auto-redirect` and `dns-hijack` in mihomo — handle via nftables manually
- This prevents DNS loops where mihomo's own queries get intercepted by its TUN interface
- Use `route-exclude-address` to exclude private CIDRs from TUN routing

## Features

- Transparent proxy for all TCP/UDP traffic from AppVMs
- DNS fake-ip mode (198.18.x.x range) with configurable filters
- GeoIP/GeoSite rule-based routing with external rule providers
- Subscription parser (Clash YAML format, vmess/vless/ss/ssr/trojan/hy2/tuic/wireguard)
- Terminal controller `clashctl` with interactive TUI + Web dashboard
- VIF interface monitoring with automatic nftables reload on VM connect

## Installation

```bash
# 1. SSH into the NetVM
ssh user@<netvm-ip>

# 2. Clone the project
git clone https://github.com/iasds/qubes-clash-gateway.git
cd qubes-clash-gateway

# 3. One-click install (mihomo + nftables + clashctl + systemd)
sudo bash setup.sh

# 4. Configure nodes — edit config or add subscription
clashctl /sub add <subscription-url>

# 5. Select routing mode
clashctl /mode rule      # Rule-based routing (recommended)

# 6. In dom0, assign AppVM to use this NetVM
qvm-prefs <appvm-name> netvm <this-netvm-name>
```

AppVMs route through this gateway automatically after installation.

## Usage

### Common Commands

```bash
clashctl /status              # Show status, traffic, node count
clashctl /mode rule           # Rule-based routing
clashctl /mode global         # Global proxy
clashctl /mode direct         # Direct connection
clashctl /sub add <url>       # Add subscription
clashctl /sub update          # Update all subscriptions
clashctl /sub list            # List subscriptions
clashctl /node                # List all nodes
clashctl /node <name>         # Select node
clashctl /test                # Speed test all nodes
clashctl /test <name>         # Speed test single node
clashctl /dns fake-ip         # Switch DNS mode
clashctl /restart             # Restart mihomo
clashctl /web                 # Start Web UI (default port 9091)
```

Aliases: `/s`=`/status`, `/m`=`/mode`, `/n`=`/node`, `/t`=`/test`

### Web UI

```bash
clashctl /web                 # Start with auto-generated token
clashctl /web --secret <pass> # Start with custom token
```

Open `http://<netvm-ip>:9091` in browser, enter token to manage.

### Test Connectivity

```bash
# On NetVM
bash scripts/test.sh

# On AppVM
curl -s https://api.ipify.org          # Exit IP
curl -s https://www.baidu.com          # Test direct connection
curl -s https://www.google.com         # Test proxied connection
```

## Persistence

Qubes AppVMs lose `/etc/` on reboot. These paths persist across restarts:

| Path | Content |
|------|---------|
| `/rw/config/clash/` | Config files, rules, subscription data |
| `/rw/config/rc.local` | Boot script (mihomo + nftables) |
| `/usr/local/bin/mihomo` | mihomo binary |
| `/etc/systemd/system/mihomo.service` | systemd service |
| `/rw/config/qubes-firewall-user-script` | Auto-reload nftables on VM connect |

## Configuration

Main config: `/rw/config/clash/config.yaml`

### Proxy Nodes

```yaml
proxies:
  - name: node1
    type: ss
    server: example.com
    port: 443
    cipher: aes-256-gcm
    password: your-password
```

Or use command: `clashctl /sub add <subscription-url>`

### Routing Rules

```yaml
rules:
  - GEOSITE,cn,DIRECT       # GeoSite match → direct
  - GEOIP,CN,DIRECT         # GeoIP match → direct
  - MATCH,auto               # Default route via auto-select
```

### Rule Providers

External rule files are auto-downloaded and cached in `/rw/config/clash/rule-providers/`:
- `geosite-cn` — Chinese domains (direct)
- `geoip-cn` — Chinese IP ranges (direct)
- `geosite-geolocation-!cn` — Non-CN domains (proxy)

## Uninstall

```bash
# Run on NetVM
sudo bash uninstall.sh
```

This will:
- Stop and remove mihomo systemd service
- Remove `/usr/local/bin/mihomo`
- Remove `/etc/sudoers.d/clashctl`
- Clean boot config from `/rw/config/rc.local`
- Remove nftables rules

Config files in `/rw/config/clash/` are preserved. Remove manually:

```bash
sudo rm -rf /rw/config/clash
```

In dom0, change AppVM netvm back:

```bash
qvm-prefs <appvm-name> netvm <original-netvm>
```

## File Structure

```
├── setup.sh                  # One-click install
├── install.sh                # Basic install (mihomo only)
├── uninstall.sh              # Uninstall
├── config/
│   ├── config.yaml           # mihomo config template
│   ├── nftables-proxy.sh     # nftables transparent proxy rules
│   └── sudoers-clashctl      # sudoers passwordless config
├── scripts/
│   └── test.sh               # Connectivity test
└── clashctl/
    ├── __main__.py            # CLI entry
    ├── api.py                 # mihomo REST API
    ├── config.py              # Constants and presets
    ├── data.py                # File I/O
    ├── i18n.py                # Internationalization
    ├── monitor.py             # Health monitoring
    ├── nodes.py               # Node parsing and speed test
    ├── parser.py              # Subscription URI parser
    ├── proxy.py               # Mode switching and service control
    ├── ui.py                  # Terminal UI
    ├── web.py                 # Web UI server
    └── web_templates/
        └── index.html         # Web UI frontend
```

## Technical Notes

### Why disable auto-redirect?

mihomo's `auto-redirect` creates nftables rules that hijack ALL traffic, including mihomo's own DNS queries going to the TUN interface. This creates a DNS loop. By disabling it and using our own nftables rules, we only intercept traffic from AppVM vif interfaces, leaving mihomo's own traffic untouched.

### Qubes vif interface lifecycle

When an AppVM starts, Qubes creates a `vif*` interface on the NetVM. Our `qcg-vif-monitor.path` systemd unit watches `/sys/class/net` for changes and reloads nftables rules to include new interfaces. The `qubes-firewall-user-script` also triggers a reload when VMs connect.

## License

MIT
