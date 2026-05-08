# Qubes Clash Gateway

English | [中文](README_CN.md)

Transparent proxy gateway for Qubes OS, powered by [mihomo](https://github.com/MetaCubeX/mihomo). Turns a NetVM into a proxy gateway — AppVMs get proxied automatically with zero configuration.

## Features

- Transparent proxy for all TCP/UDP traffic
- DNS fake-ip to prevent pollution (198.18.x.x)
- GeoIP rule-based routing (CN direct, foreign proxy)
- Subscription parser (Clash YAML, vmess/vless/ss/ssr/trojan/hy2/tuic/wireguard)
- Terminal controller `clashctl` + Web UI

## Installation

```bash
# 1. SSH into the NetVM
ssh user@<netvm-ip>

# 2. Clone the project
git clone https://github.com/iasds/qubes-clash-gateway.git
cd qubes-clash-gateway

# 3. One-click install (mihomo + nftables + clashctl + systemd)
sudo bash setup.sh

# 4. Add subscription
clashctl /sub add <subscription-url>

# 5. Select mode
clashctl /mode rule      # Rule-based routing (recommended)

# 6. In dom0, assign AppVM to use this NetVM
qvm-prefs <appvm-name> netvm <this-netvm-name>
```

AppVMs can access the internet immediately after installation.

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
curl -s https://api.ipify.org          # Exit IP (should be proxy server)
curl -s https://www.baidu.com          # CN direct
curl -s https://www.google.com         # Foreign proxy
```

## Architecture

```
AppVM → vif* interface → nftables redirect → mihomo
                                           ├→ DNS :53 → :1053 (fake-ip)
                                           ├→ TCP  → :7892 (redir-port)
                                           └→ UDP  → :7893 (tproxy-port)

mihomo routing:
  ├→ CN domains/IPs → direct
  └→ Foreign → proxy nodes → internet
```

## Persistence

Qubes AppVMs lose `/etc/` on reboot. These paths persist:

| Path | Content |
|------|---------|
| `/rw/config/clash/` | Config files, rules, subscription data |
| `/rw/config/rc.local` | Boot script (mihomo + nftables) |
| `/usr/local/bin/mihomo` | mihomo binary |
| `/etc/systemd/system/mihomo.service` | systemd service |

## Configuration

Main config: `/rw/config/clash/config.yaml`

### Add Proxy Nodes

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
  - GEOSITE,cn,DIRECT       # CN domains direct
  - GEOIP,CN,DIRECT         # CN IPs direct
  - MATCH,auto               # Rest via proxy
```

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

## License

MIT
