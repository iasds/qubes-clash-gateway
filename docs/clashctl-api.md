# clashctl CLI Reference

`clashctl` is the command-line controller for qubes-clash-gateway. It communicates
with mihomo's REST API (default `http://127.0.0.1:9090`) to manage proxy
configuration, subscriptions, nodes, and DNS settings.

## Usage

```bash
clashctl /<command> [arguments...]
```

All commands start with `/`. Short aliases are available (see below).

---

## Commands

### `/status`

Show the current status of the gateway.

| Attribute | Value |
|-----------|-------|
| Alias | `/s` |
| Arguments | None |
| Output | Formatted status block |

**Output fields:**
- `mihomo` — `running` or `stopped`
- `version` — mihomo version string (e.g., `v1.19.0`)
- `mode` — Current proxy mode (`RULE`, `GLOBAL`, or `DIRECT`)
- `exit IP` — Public IP seen by external services (queried through proxy)
- `DNS` — DNS enhanced-mode and listen port
- `nodes` — Total proxy node count
- `active` — Currently selected node and its group
- `subs` — Number of subscriptions with last-update timestamps

**Example:**
```
$ clashctl /status

  qubes-clash-gateway
  ────────────────────────────────────────
  mihomo:     running
  version:    v1.19.0
  mode:       ◐ RULE
  exit IP:    203.0.113.42
  DNS:        fake-ip @ :1053
  nodes:      15
  active:     node-jp-01 (in auto)
  subs:       1
    • sub-06021430  2h ago
  ────────────────────────────────────────
```

**Exit codes:** 0 always

---

### `/mode`

Switch the proxy routing mode.

| Attribute | Value |
|-----------|-------|
| Alias | `/m` |
| Arguments | `global`, `rule`, or `direct` (optional — shows current mode if omitted) |
| Output | Confirmation or current mode display |

**Modes:**
- `rule` — Rule-based routing (recommended). Uses GeoIP/GeoSite rules to split
  traffic between DIRECT and proxy. Default preset: `smart-split`.
- `global` — All traffic through proxy. Creates a `GLOBAL` select group with all
  nodes for manual selection.
- `direct` — All traffic goes DIRECT (no proxy). Useful for troubleshooting.

**Behavior:** Rewrites `config.yaml` with the appropriate proxy-groups and rules,
then reloads mihomo via the API. If the API is unreachable, restarts the mihomo
systemd service.

**Examples:**
```bash
clashctl /mode           # Show current mode
clashctl /mode rule      # Switch to rule-based routing
clashctl /mode global    # Switch to global proxy
clashctl /mode direct    # Switch to direct (no proxy)
```

**Exit codes:** 0 on success, prints error message on invalid mode

---

### `/node`

List or select proxy nodes.

| Attribute | Value |
|-----------|-------|
| Alias | `/n` |
| Arguments | Optional node name (space-separated if multi-word) |
| Output | Node list or switch confirmation |

**Without arguments:** Lists all proxy groups and their member nodes. The currently
selected node in each group is marked with `→`.

**With arguments:** Switches the active node in the appropriate proxy group.
Searches all groups for the node name; falls back to the `GLOBAL` group.

**Examples:**
```bash
clashctl /node                    # List all groups and nodes
clashctl /node node-jp-01         # Switch to node-jp-01
clashctl /node "US West 02"       # Switch to a node with spaces in name
```

**Output (list mode):**
```
  auto (URLTest)
    Current: node-jp-01
    → node-jp-01
      node-us-01
      node-sg-01
```

**Exit codes:** 0 on success

---

### `/test`

Run latency tests on proxy nodes.

| Attribute | Value |
|-----------|-------|
| Alias | `/t` |
| Arguments | Optional node name (tests all nodes if omitted) |
| Output | Latency results per node |

**Behavior:** Uses mihomo's proxy delay API (`GET /proxies/:name/delay`) with
the Google `generate_204` URL. Tests run concurrently (up to 15 workers).

**Delay color coding:**
- Green: < 200ms
- Default: 200–500ms
- Red: > 500ms or timeout

**Examples:**
```bash
clashctl /test                    # Test all nodes
clashctl /test node-jp-01         # Test single node
clashctl /test "US West 02"       # Test node with spaces
```

**Output:**
```
→ Testing speed...

  ● node-jp-01: 89ms
  ● node-sg-01: 156ms
  ○ node-us-01: timeout
```

**Exit codes:** 0 always (even if some nodes timeout)

---

### `/sub add`

Add a subscription URL.

| Attribute | Value |
|-----------|-------|
| Alias | None |
| Arguments | `<url>` (required) — Subscription URL (Clash YAML format or base64-encoded URI list) |
| Output | Node count added |

**Behavior:**
1. Fetches the subscription URL
2. Parses the response (supports Clash YAML, vmess://, ss://, ssr://, trojan://,
   hy2://, tuic://, anytls:// URIs)
3. Merges new nodes into the existing proxy list (deduplicates by name)
4. Saves subscription metadata to `clashctl-subscriptions.json`
5. Reloads mihomo config

**Supported protocols:** vmess, vless, shadowsocks (ss), shadowsocksR (ssr),
trojan, hysteria2 (hy2), tuic, anytls, wireguard

**Example:**
```bash
clashctl /sub add https://example.com/api/clash/sub?token=abc123
```

**Output:**
```
→ Fetching subscription...
✓ Added 15 nodes (12 new)
```

**Exit codes:** 0 on success, non-zero on fetch/parse failure

---

### `/sub update`

Update all subscriptions.

| Attribute | Value |
|-----------|-------|
| Alias | None |
| Arguments | None |
| Output | Per-subscription results |

**Behavior:**
1. Loads all saved subscriptions from `clashctl-subscriptions.json`
2. Re-fetches each subscription URL
3. Replaces the entire proxy list with freshly-fetched nodes
4. Re-applies the current mode to rebuild proxy-groups and rules
5. Saves updated metadata

**Example:**
```bash
clashctl /sub update
```

**Output:**
```
→ Updating sub-06021430...
✓   15 nodes
✓ Total 15 nodes updated
```

**Exit codes:** 0 always (individual failures are reported but don't halt)

---

### `/sub list`

List saved subscriptions.

| Attribute | Value |
|-----------|-------|
| Alias | None |
| Arguments | None |
| Output | Subscription list |

**Example:**
```bash
clashctl /sub list
```

**Output:**
```
  • sub-06021430  15 nodes  2h ago
    https://example.com/api/clash/sub?token=...
```

**Exit codes:** 0 always

---

### `/sub remove`

Remove a subscription by name.

| Attribute | Value |
|-----------|-------|
| Alias | None |
| Arguments | `<name>` (required) — Subscription name (e.g., `sub-06021430`) |
| Output | Deletion confirmation |

**Note:** This removes the subscription record but does NOT remove the proxy nodes
from the config. To also remove nodes, use `/sub update` after removal or manually
edit `config.yaml`.

**Example:**
```bash
clashctl /sub remove sub-06021430
```

**Exit codes:** 0 on success, non-zero if subscription not found

---

### `/dns`

Switch the DNS enhanced mode.

| Attribute | Value |
|-----------|-------|
| Alias | None |
| Arguments | `fake-ip` or `redir-host` (required) |
| Output | Confirmation |

**DNS modes:**
- `fake-ip` (recommended) — mihomo returns fake IPs (198.18.0.0/16 range) for
  domain queries. When an application connects to the fake IP, mihomo maps it
  back to the real domain. Enables domain-based routing rules and prevents DNS
  pollution. Includes a fake-ip-filter list for domains that need real IPs
  (NTP, STUN, local domains).
- `redir-host` — mihomo resolves the real IP upstream and returns it. Better
  compatibility but no domain-based routing and susceptible to DNS pollution.

**Behavior:** Rewrites the `dns` section in `config.yaml` with the selected
preset's nameserver, fallback, and filter configuration. Reloads mihomo.

**Examples:**
```bash
clashctl /dns fake-ip       # Switch to fake-ip mode
clashctl /dns redir-host    # Switch to redir-host mode
```

**Exit codes:** 0 on success, non-zero for invalid mode

---

### `/restart`

Restart the mihomo service.

| Attribute | Value |
|-----------|-------|
| Alias | `/r` |
| Arguments | None |
| Output | Confirmation |

**Behavior:** Runs `sudo systemctl restart mihomo`. The sudoers configuration at
`/rw/config/sudoers.d/clashctl` allows this without a password.

**Example:**
```bash
clashctl /restart
```

**Output:**
```
→ Restarting mihomo...
✓ Restarted
```

**Exit codes:** 0 on success, non-zero on failure

---

### `/help`

Show the help message.

| Attribute | Value |
|-----------|-------|
| Alias | `/h` |
| Arguments | None |
| Output | Formatted command list |

**Example:**
```bash
clashctl /help
```

**Output:**
```
  clashctl — qubes-clash-gateway controller
  ────────────────────────────────────────
  /status              Show status
  /mode global|rule|direct  Switch mode
  /sub add <url>       Add subscription
  /sub update          Update all subscriptions
  /sub list            List subscriptions
  /sub remove <name>   Remove subscription
  /node                List all nodes
  /node <name>         Select node
  /test [node]         Speed test
  /dns fake-ip|redir-host  Switch DNS mode
  /restart             Restart mihomo
  /help                Show help
  /web [port]          Start Web UI (default 9091)
  ────────────────────────────────────────
  alias: /s=/status /m=/mode /n=/node /t=/test
```

---

### `/web`

Start the Web UI dashboard.

| Attribute | Value |
|-----------|-------|
| Alias | `/w` |
| Arguments | `[port]` (default: 9091), `[--secret <password>]`, `[--no-auth]` |
| Output | Server startup message (foreground process) |

**Behavior:** Starts a lightweight HTTP server (Python `http.server`) serving a
single-page dashboard. The Web UI provides a graphical interface for:
- Viewing proxy status and traffic
- Switching proxy modes
- Selecting nodes
- Running speed tests
- Managing subscriptions

**Authentication:** By default, auto-generates a random token displayed at startup.
Use `--secret <password>` to set a custom token, or `--no-auth` to disable
authentication entirely.

**Examples:**
```bash
clashctl /web                       # Start on port 9091, auto-generated token
clashctl /web 8080                  # Start on port 8080
clashctl /web --secret mypassword   # Custom authentication token
clashctl /web --no-auth             # No authentication (local use only)
```

**Access:** Open `http://<netvm-ip>:9091` in a browser from any Qubes VM.

**Exit codes:** Runs as a foreground server (Ctrl+C to stop)

---

## Alias Reference

| Alias | Full Command |
|-------|-------------|
| `/s` | `/status` |
| `/m` | `/mode` |
| `/n` | `/node` |
| `/t` | `/test` |
| `/h` | `/help` |
| `/r` | `/restart` |
| `/w` | `/web` |

## Configuration Paths

| Path | Content |
|------|---------|
| `/rw/config/clash/config.yaml` | mihomo configuration (proxies, DNS, rules, TUN) |
| `/rw/config/clash/clashctl-subscriptions.json` | Subscription metadata |
| `/rw/config/clash/clashctl-preferences.json` | User preferences (mode, DNS preset, language) |
| `/rw/config/clash/clashctl-custom-rules.yaml` | Custom routing rules |
| `/rw/config/clash/rule-providers/` | Cached GeoSite/GeoIP rule files |

## API Integration

clashctl communicates with mihomo via its external-controller REST API:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/version` | GET | Version check (health) |
| `/configs` | GET | Current config |
| `/configs` | PATCH | Update mode/log-level/etc. |
| `/configs` | PUT | Reload config from file |
| `/proxies` | GET | List all proxies and groups |
| `/proxies/:name` | PUT | Switch active proxy in group |
| `/proxies/:name/delay` | GET | Test proxy latency |
| `/connections` | GET | Active connections |
| `/cache/dns/flush` | POST | Flush DNS cache |
| `/providers/proxies` | GET | Proxy providers |

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `QCG_API_SECRET` | (read from config.yaml) | Override mihomo API secret |
