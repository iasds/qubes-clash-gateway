#!/bin/bash
# qubes-clash-gateway connectivity test script
# Run on NetVM: test if proxy is working properly
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
pass() { echo -e "  ${GREEN}✓${NC} $*"; }
fail() { echo -e "  ${RED}✗${NC} $*"; }
warn() { echo -e "  ${YELLOW}!${NC} $*"; }

PROXY="socks5h://127.0.0.1:7890"
TIMEOUT=10

echo ""
echo "=== qubes-clash-gateway Connectivity Test ==="
echo ""

# 1. Check mihomo process
echo "1. Service Status"
if systemctl is-active --quiet mihomo 2>/dev/null; then
    pass "mihomo service is running"
else
    fail "mihomo service is not running"
    echo "     Try: sudo systemctl start mihomo"
fi

# 2. Check port listening
echo ""
echo "2. Port Listening"
if ss -tlnp | grep -q ":7890"; then
    pass "Proxy port 7890 is listening"
else
    fail "Proxy port 7890 is not listening"
fi
if ss -ulnp | grep -q ":1053"; then
    pass "DNS port 1053 is listening"
else
    fail "DNS port 1053 is not listening"
fi

# 3. TUN interface
echo ""
echo "3. TUN Interface"
if ip link show Meta 2>/dev/null || ip link show tun0 2>/dev/null || ip link show mihomo 2>/dev/null; then
    pass "TUN interface exists"
else
    warn "TUN interface not detected (may use a different name)"
fi

# 4. Direct connection test via proxy (domestic site)
echo ""
echo "4. Domestic Direct Connection Test"
code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout $TIMEOUT -x "$PROXY" "https://www.baidu.com" 2>/dev/null || echo "000")
if [ "$code" = "200" ] || [ "$code" = "302" ]; then
    pass "baidu.com → HTTP $code"
else
    fail "baidu.com → HTTP $code"
fi

# 5. Proxy forwarding test (overseas site)
echo ""
echo "5. Proxy Forwarding Test"
code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout $TIMEOUT -x "$PROXY" "https://www.google.com" 2>/dev/null || echo "000")
if [ "$code" = "200" ] || [ "$code" = "302" ]; then
    pass "google.com → HTTP $code"
else
    fail "google.com → HTTP $code"
fi

# 6. Exit IP
echo ""
echo "6. Exit IP"
ip=$(curl -s --connect-timeout $TIMEOUT -x "$PROXY" "https://api.ipify.org" 2>/dev/null || echo "Failed to retrieve")
if [ "$ip" != "Failed to retrieve" ] && [ -n "$ip" ]; then
    pass "Exit IP: $ip"
else
    fail "Unable to get exit IP"
fi

# 7. DNS resolution (fake-ip test)
echo ""
echo "7. DNS Resolution"
dns_result=$(python3 -c '
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.settimeout(3)
pkt = b"\x00\x01\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x06google\x03com\x00\x00\x01\x00\x01"
s.sendto(pkt, ("127.0.0.1", 1053))
r = s.recv(512)
ip = ".".join(str(b) for b in r[-4:])
print(ip)
' 2>/dev/null || echo "")
if [ -n "$dns_result" ]; then
    pass "DNS resolution: google.com → $dns_result"
    if echo "$dns_result" | grep -q "^198\\.18\\."; then
        pass "fake-ip mode active (198.18.x.x)"
    else
        warn "Not a fake-ip address, may be using redir-host mode"
    fi
else
    # fallback: try dig
    dns_result=$(dig +short @127.0.0.1 -p 1053 google.com 2>/dev/null || echo "")
    if [ -n "$dns_result" ]; then
        pass "DNS resolution: google.com → $dns_result"
    else
        fail "DNS resolution failed"
    fi
fi

echo ""
echo "=== Test Complete ==="
echo ""
echo "If AppVM cannot access the internet, verify in dom0:"
echo "  qvm-prefs <appvm-name> netvm $(hostname)"
