# Qubes Clash Gateway

[English](README.md) | **[中文](README_zh.md)**

Qubes OS transparent proxy gateway powered by [mihomo](https://github.com/MetaCubeX/mihomo). Turns a Qubes NetVM into a proxy gateway — any AppVM using it as NetVM gets proxied automatically, zero AppVM-side configuration.

## Verified Working

| Feature | Status |
|---------|--------|
| Transparent proxy (TCP/UDP, all ports) | ✅ |
| DNS fake-ip (198.18.x.x) | ✅ |
| GeoIP rule-based routing (CN direct, foreign proxy) | ✅ |
| nftables DNS hijack on vif* interfaces | ✅ |
| mihomo TUN auto-route | ✅ |
| systemd service + rc.local persistence | ✅ |
| clashctl terminal control | ✅ |
| Subscription parser (Clash YAML, vmess/ss/ssr/trojan/hy2/tuic) | ✅ |

## Quick Start

```bash
# 1. Clone to NetVM
git clone https://github.com/iasds/qubes-clash-gateway.git
cd qubes-clash-gateway

# 2. Install (auto-detects Qubes NetVM, installs mihomo, configures nftables)
sudo bash setup.sh

# 3. Add subscription
clashctl /sub add <your-subscription-url>

# 4. Select mode
clashctl /mode rule    # Rule-based (recommended)
clashctl /mode global  # Global proxy
clashctl /mode direct  # Direct connection

# 5. In dom0, assign AppVM
qvm-prefs <appvm-name> netvm <this-netvm-name>
```

## Architecture

```
AppVM → vif* interface → nftables (DNS hijack :53→:1053) → mihomo TUN
                                                          ├→ CN domains/IPs → direct via eth0
                                                          └→ Foreign → proxy nodes → upstream → internet
```

## Commands

```bash
clashctl /status          # Show status, traffic, nodes
clashctl /mode rule       # Rule-based routing
clashctl /mode global     # Global proxy
clashctl /mode direct     # Direct connection
clashctl /sub add <url>   # Add subscription
clashctl /node <name>     # Select specific node
clashctl /test            # Speed test nodes
clashctl /dns             # Show DNS config
clashctl /restart         # Restart mihomo
```

## Files

```
├── setup.sh              # One-click install (recommended)
├── install.sh            # Basic install (no nftables)
├── uninstall.sh          # Uninstall
├── config/
│   └── config.yaml       # mihomo config template
├── scripts/
│   └── test.sh           # Connectivity test
└── clashctl/
    ├── __main__.py       # CLI entry point
    ├── api.py            # mihomo REST API client
    ├── config.py         # Constants, paths, presets
    ├── data.py           # JSON/YAML file I/O
    ├── i18n.py           # zh/en translations
    ├── monitor.py        # Health monitoring daemon
    ├── nodes.py          # Node parsing, speed test, GeoIP
    ├── parser.py         # Subscription parser (vmess/vless/ss/ssr/trojan/hy2/tuic/wg)
    ├── proxy.py          # Mode switching, DNS config, service control
    ├── ui.py             # Terminal UI
    ├── web.py            # Web UI server
    └── web_templates/
        └── index.html    # Web UI (dark mode SPA)
```

## Key Design Decisions

**DNS loop prevention**: mihomo's built-in `dns-hijack` creates a loop (mihomo's own DNS → TUN → fake-ip → mihomo). Solved by:
- Disabling `dns-hijack` and `auto-redirect` in mihomo config
- Manual nftables rules that only hijack DNS from `vif*` (AppVM) interfaces
- `direct-nameserver` for mihomo's own DNS resolution

**Persistence**: Qubes AppVMs lose `/etc/` on reboot:
- `/rw/config/clash/` — Config and rule files (persistent)
- `/rw/config/rc.local` — Boot script (starts mihomo + loads nftables)
- `/usr/local/bin/mihomo` — Binary (persistent)

## Uninstall

```bash
sudo bash uninstall.sh
```

## License

MIT
