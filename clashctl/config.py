"""Constants and paths for clashctl"""
import os

# Paths (Qubes persistent storage)
CLASH_DIR = "/rw/config/clash"
CONFIG_YAML = os.path.join(CLASH_DIR, "config.yaml")
PREFERENCES_JSON = os.path.join(CLASH_DIR, "clashctl-preferences.json")
SUBSCRIPTIONS_JSON = os.path.join(CLASH_DIR, "clashctl-subscriptions.json")
CUSTOM_RULES_YAML = os.path.join(CLASH_DIR, "clashctl-custom-rules.yaml")
RULE_PROVIDERS_DIR = os.path.join(CLASH_DIR, "rule-providers")

# mihomo API
API_BASE = "http://127.0.0.1"
API_PORT = 9090
API_SECRET = ""  # No secret by default on localhost

# Speedtest
DEFAULT_SPEEDTEST_URL = "https://www.gstatic.com/generate_204"
DEFAULT_UPDATE_INTERVAL_HOURS = 6
SPEEDTEST_TIMEOUT = 3
SPEEDTEST_WORKERS = 15

# ANSI colors
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_RED = "\033[31m"
C_CYAN = "\033[36m"
C_GRAY = "\033[90m"
C_WHITE = "\033[97m"

# Box drawing
BOX_W = 58

# ── Rule Providers (mihomo external rule files) ──
# Downloaded once, cached in rule-providers/, auto-updated.
RULE_PROVIDERS = {
    "geosite-cn": {
        "type": "http",
        "behavior": "domain",
        "url": "https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/release/geosite/cn.yaml",
        "path": "./rule-providers/geosite-cn.yaml",
        "interval": 86400,
    },
    "geoip-cn": {
        "type": "http",
        "behavior": "ipcidr",
        "url": "https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/release/geoip/cn.yaml",
        "path": "./rule-providers/geoip-cn.yaml",
        "interval": 86400,
    },
    "geosite-ads": {
        "type": "http",
        "behavior": "domain",
        "url": "https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/release/geosite/category-ads-all.yaml",
        "path": "./rule-providers/geosite-ads.yaml",
        "interval": 86400,
    },
}

# Private IP CIDRs
PRIVATE_CIDRS = [
    "10.0.0.0/8",
    "100.64.0.0/10",
    "127.0.0.0/8",
    "169.254.0.0/16",
    "172.16.0.0/12",
    "192.168.0.0/16",
]

# ── Rule presets ──
RULE_PRESETS = {
    "smart-split": {
        "name": "智能分流",
        "desc": "中国直连，国外自动选节点",
        "rules": [
            "RULE-SET,geosite-ads,REJECT",
            "RULE-SET,geosite-cn,DIRECT",
            "RULE-SET,geoip-cn,DIRECT",
            "GEOIP,private,DIRECT",
            "MATCH,auto",
        ],
    },
    "all-proxy": {
        "name": "全部代理",
        "desc": "所有流量走自动选节点",
        "rules": [
            "GEOIP,private,DIRECT",
            "MATCH,auto",
        ],
    },
    "bypass-cn": {
        "name": "仅代理受限",
        "desc": "只代理已知受限站点",
        "rules": [
            "RULE-SET,geosite-ads,REJECT",
            "DOMAIN-SUFFIX,google.com,auto",
            "DOMAIN-SUFFIX,googleapis.com,auto",
            "DOMAIN-SUFFIX,youtube.com,auto",
            "DOMAIN-SUFFIX,twitter.com,auto",
            "DOMAIN-SUFFIX,x.com,auto",
            "DOMAIN-SUFFIX,facebook.com,auto",
            "DOMAIN-SUFFIX,instagram.com,auto",
            "DOMAIN-SUFFIX,wikipedia.org,auto",
            "DOMAIN-SUFFIX,github.com,auto",
            "DOMAIN-SUFFIX,githubusercontent.com,auto",
            "DOMAIN-SUFFIX,telegram.org,auto",
            "DOMAIN-SUFFIX,t.me,auto",
            "DOMAIN-SUFFIX,openai.com,auto",
            "DOMAIN-SUFFIX,anthropic.com,auto",
            "DOMAIN-SUFFIX,reddit.com,auto",
            "DOMAIN-SUFFIX,medium.com,auto",
            "DOMAIN-SUFFIX,netflix.com,auto",
            "DOMAIN-SUFFIX,spotify.com,auto",
            "DOMAIN-KEYWORD,google,auto",
            "DOMAIN-KEYWORD,youtube,auto",
            "DOMAIN-KEYWORD,twitter,auto",
            "DOMAIN-KEYWORD,facebook,auto",
            "DOMAIN-KEYWORD,telegram,auto",
            "RULE-SET,geoip-cn,DIRECT",
            "GEOIP,private,DIRECT",
            "MATCH,DIRECT",
        ],
    },
}

# ── DNS presets ──
DNS_PRESETS = {
    "fake-ip": {
        "name": "Fake-IP（推荐）",
        "desc": "防DNS污染，CN域名fallback直连",
        "enhanced-mode": "fake-ip",
        "fake-ip-range": "198.18.0.1/16",
        "nameserver": [
            "https://cloudflare-dns.com/dns-query",
            "https://dns.google/dns-query",
        ],
        "fallback": [
            "https://1.1.1.1/dns-query",
            "tls://8.8.8.8:853",
        ],
        "fallback-filter": {
            "geoip": True,
            "geoip-code": "CN",
            "ipcidr": ["240.0.0.0/4"],
            "domain": ["+.google.com", "+.facebook.com", "+.youtube.com"],
        },
        "fake-ip-filter": [
            "*.lan",
            "*.localdomain",
            "*.example",
            "*.invalid",
            "*.localhost",
            "*.test",
            "*.local",
            "*.home.arpa",
            "time.*.com",
            "time.*.gov",
            "time.*.edu.cn",
            "time.*.apple.com",
            "time-ios.apple.com",
            "time1.*.com",
            "time2.*.com",
            "time3.*.com",
            "time4.*.com",
            "time5.*.com",
            "time6.*.com",
            "time7.*.com",
            "ntp.*.com",
            "ntp1.*.com",
            "ntp2.*.com",
            "ntp3.*.com",
            "ntp4.*.com",
            "ntp5.*.com",
            "ntp6.*.com",
            "ntp7.*.com",
            "*.time.edu.cn",
            "*.ntp.org.cn",
            "+.pool.ntp.org",
            "time1.cloud.tencent.com",
            "stun.*.*",
            "stun.*.*.*",
            "+.stun.*.*",
            "+.stun.*.*.*",
            "+.stun.*.*.*.*",
            "+.stun.*.*.*.*.*",
        ],
    },
    "redir-host": {
        "name": "Redir-Host",
        "desc": "传统模式，兼容性好",
        "enhanced-mode": "redir-host",
        "nameserver": [
            "https://cloudflare-dns.com/dns-query",
            "https://dns.google/dns-query",
        ],
        "fallback": [
            "https://1.1.1.1/dns-query",
            "tls://8.8.8.8:853",
        ],
        "fallback-filter": {
            "geoip": True,
            "geoip-code": "CN",
        },
    },
}

# mihomo proxy type mapping from URI scheme
URI_TYPE_MAP = {
    "ss": "ss",
    "shadowsocks": "ss",
    "vmess": "vmess",
    "vless": "vless",
    "trojan": "trojan",
    "hysteria2": "hysteria2",
    "hysteria": "hysteria2",
    "hy2": "hysteria2",
    "tuic": "tuic",
    "anytls": "anytls",
    "wireguard": "wireguard",
    "wg": "wireguard",
}
