# Qubes Clash Gateway

[English](README.md) | **[中文](README_zh.md)**

Qubes OS transparent proxy gateway powered by [mihomo](https://github.com/MetaCubeX/mihomo). Zero-config for AppVMs — all traffic (TCP/UDP, all ports) is automatically proxied through the gateway.

## Why?

Qubes OS isolates VMs but doesn't solve the proxy problem. Running a proxy client in every AppVM is tedious. This project turns a Qubes NetVM into a transparent proxy gateway — any AppVM that uses it as its NetVM gets proxied automatically, with zero configuration on the AppVM side.

**Compared to sing-box TUN approach** (previous project `qubes-singroute-gateway`):

| Feature | sing-box | mihomo |
|---------|----------|--------|
| Auto nftables config | ❌ Manual | ✅ `auto-redirect` |
| DNS hijacking | ❌ External forwarder needed | ✅ Built-in `dns-hijack` |
| Fake-IP DNS | ❌ Not supported | ✅ Built-in |
| Gateway documentation | ❌ None | ✅ "Works as expected on routers" |
| Routing stability | ❌ Multiple edge cases | ✅ Battle-tested with Clash |

## Quick Start

```bash
# 1. Download mihomo binary from https://github.com/MetaCubeX/mihomo/releases
#    Select: linux-amd64 .gz file
#    Place it in this directory as mihomo.gz or /tmp/mihomo.gz

# 2. Install
sudo bash install.sh

# 3. Add subscription
# Edit /rw/config/clash/config.yaml — add your proxy nodes under 'proxies:'

# 4. Restart
sudo systemctl restart mihomo

# 5. Test from NetVM
bash scripts/test.sh

# 6. In dom0, assign AppVM to use this NetVM
qvm-prefs <appvm-name> netvm <this-netvm-name>
```

## Architecture

```
AppVM (any) → NetVM (sys-clash)
    ↓ ALL traffic arrives on vif* interface
mihomo TUN (auto-redirect handles nftables)
    ├→ CN domains/IPs → direct out eth0
    └→ Foreign → proxy nodes → upstream NetVM → internet
```

## Files

```
├── install.sh              # Install script
├── uninstall.sh            # Uninstall script
├── config/
│   └── config.yaml         # mihomo config template
├── scripts/
│   └── test.sh             # Connectivity test
└── clashctl/               # TUI management tool (planned)
```

## Persistence

Qubes AppVMs lose `/etc/` on reboot. This project handles persistence via:

- **`/rw/config/clash/`** — Config files (persistent)
- **`/rw/config/rc.local`** — Boot script that starts mihomo and brings up vif interfaces
- **`/usr/local/bin/mihomo`** — Binary (persistent in AppVM)

## Configuration

Edit `/rw/config/clash/config.yaml`:

### Add Subscription

```yaml
proxy-groups:
  - name: auto
    type: url-test
    proxies:
      - node-1
      - node-2
    url: https://www.gstatic.com/generate_204
    interval: 300
```

### DNS Modes

- **`fake-ip`** (recommended): Returns fake IPs (198.18.x.x), prevents DNS pollution
- **`redir-host`**: Returns real IPs, compatible with more applications

## Uninstall

```bash
sudo bash uninstall.sh
```

## License

MIT
