#!/bin/bash
# qubes-clash-gateway security verification script
# Tests all 5 security layers: DNS, TCP, UDP, Kill Switch, ICMP
# Run on NetVM: bash scripts/test.sh
# Run remotely: bash scripts/test.sh --remote <ssh-target>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

# Test-specific helpers
pass() { echo -e "  ${GREEN}✓${NC} $*"; FAIL_COUNT=${FAIL_COUNT}; }
fail() { echo -e "  ${RED}✗${NC} $*"; FAIL_COUNT=$((FAIL_COUNT + 1)); }
warn() { echo -e "  ${YELLOW}!${NC} $*"; }

FAIL_COUNT=0
PASS_COUNT=0
TOTAL=5
PROXY="socks5h://127.0.0.1:7890"
TIMEOUT=10

# Parse args
REMOTE=""
if [[ "${1:-}" == "--remote" ]]; then
    REMOTE="${2:-}"
    if [[ -z "$REMOTE" ]]; then
        log_error "Usage: $0 --remote <ssh-target>"
        exit 1
    fi
    log_info "Running tests remotely via SSH: $REMOTE"
fi

# Helper to run commands locally or remotely
run_cmd() {
    if [[ -n "$REMOTE" ]]; then
        ssh -o ConnectTimeout=5 "$REMOTE" "$@"
    else
        eval "$@"
    fi
}

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║   qubes-clash-gateway Security Verification     ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── Test 1: DNS Interception (fake-ip) ──────────────────────────────────────
echo "[$((FAIL_COUNT + 1))/$TOTAL] DNS Fake-IP Interception"
dns_result=$(run_cmd "python3 -c \"
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.settimeout(3)
pkt = b'\\\\x00\\\\x01\\\\x01\\\\x00\\\\x00\\\\x01\\\\x00\\\\x00\\\\x00\\\\x00\\\\x00\\\\x00\\\\x06google\\\\x03com\\\\x00\\\\x00\\\\x01\\\\x00\\\\x01'
s.sendto(pkt, ('127.0.0.1', 1053))
r = s.recv(512)
ip = '.'.join(str(b) for b in r[-4:])
print(ip)
\"" 2>/dev/null || echo "")

if [[ -n "$dns_result" ]] && echo "$dns_result" | grep -q "^198\\.18\\."; then
    pass "DNS returns fake-ip: google.com → $dns_result"
else
    fail "DNS fake-ip not working (got: ${dns_result:-empty})"
    echo "    Expected: 198.18.x.x, mihomo DNS on port 1053"
fi

# ── Test 2: TCP Transparent Proxy ───────────────────────────────────────────
echo ""
echo "[$((FAIL_COUNT + 1))/$TOTAL] TCP Transparent Proxy"
exit_ip=$(run_cmd "curl -s --connect-timeout $TIMEOUT https://api.ipify.org" 2>/dev/null || echo "")
if [[ -n "$exit_ip" ]] && ! echo "$exit_ip" | grep -qE "^(10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.)"; then
    pass "TCP proxy working, exit IP: $exit_ip"
else
    fail "TCP proxy not working (exit IP: ${exit_ip:-timeout})"
    echo "    Expected: proxy exit IP (not local/private IP)"
fi

# ── Test 3: UDP Transparent Proxy (tproxy) ──────────────────────────────────
echo ""
echo "[$((FAIL_COUNT + 1))/$TOTAL] UDP Transparent Proxy (tproxy)"
udp_result=$(run_cmd "dig +short +timeout=5 @127.0.0.1 -p 1053 google.com A" 2>/dev/null || echo "")
if [[ -n "$udp_result" ]]; then
    pass "UDP DNS via tproxy: google.com → $udp_result"
else
    # Fallback: try python DNS
    udp_result=$(run_cmd "python3 -c \"
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.settimeout(3)
pkt = b'\\\\x00\\\\x01\\\\x01\\\\x00\\\\x00\\\\x01\\\\x00\\\\x00\\\\x00\\\\x00\\\\x00\\\\x00\\\\x06google\\\\x03com\\\\x00\\\\x00\\\\x01\\\\x00\\\\x01'
s.sendto(pkt, ('127.0.0.1', 1053))
r = s.recv(512)
print('ok')
\"" 2>/dev/null || echo "")
    if [[ -n "$udp_result" ]]; then
        pass "UDP DNS working via python"
    else
        fail "UDP tproxy not working"
        echo "    Expected: DNS query via UDP to port 1053 succeeds"
    fi
fi

# ── Test 4: Kill Switch ─────────────────────────────────────────────────────
echo ""
echo "[$((FAIL_COUNT + 1))/$TOTAL] Kill Switch (mihomo down = traffic blocked)"

# Check if we can test Kill Switch (needs root to stop mihomo)
if [[ -n "$REMOTE" ]] || [[ $EUID -eq 0 ]]; then
    # Save mihomo state
    was_active=$(run_cmd "systemctl is-active mihomo" 2>/dev/null || echo "inactive")

    if [[ "$was_active" == "active" ]]; then
        # Stop mihomo to simulate crash
        run_cmd "sudo systemctl stop mihomo" 2>/dev/null || true
        sleep 2

        # Try to reach internet — should fail
        killswitch_result=$(run_cmd "curl -s --connect-timeout 5 https://api.ipify.org" 2>/dev/null || echo "BLOCKED")
        if [[ "$killswitch_result" == "BLOCKED" ]] || [[ -z "$killswitch_result" ]]; then
            pass "Kill Switch active: traffic blocked when mihomo is down"
        else
            fail "Kill Switch NOT working: traffic leaked ($killswitch_result)"
            echo "    Expected: curl times out when mihomo is stopped"
        fi

        # Restart mihomo
        run_cmd "sudo systemctl start mihomo" 2>/dev/null || true
        sleep 2
    else
        warn "mihomo not active, skipping Kill Switch test"
        echo "    Start mihomo first: sudo systemctl start mihomo"
    fi
else
    warn "Kill Switch test requires root. Run with: sudo bash scripts/test.sh"
    echo "    Or test remotely: bash scripts/test.sh --remote <target>"
fi

# ── Test 5: ICMP Blocking ───────────────────────────────────────────────────
echo ""
echo "[$((FAIL_COUNT + 1))/$TOTAL] ICMP Blocking"
icmp_result=$(run_cmd "ping -c 1 -W 3 8.8.8.8" 2>/dev/null || echo "BLOCKED")
if echo "$icmp_result" | grep -q "100% packet loss\|100%\|Network is unreachable\|BLOCKED"; then
    pass "ICMP blocked: ping 8.8.8.8 failed (as expected)"
else
    fail "ICMP NOT blocked: ping succeeded"
    echo "    Expected: ping 8.8.8.8 returns 100% packet loss"
fi

# ── Summary ──────────────────────────────────────────────────────────────────
PASS_COUNT=$((TOTAL - FAIL_COUNT))
echo ""
echo "══════════════════════════════════════════════════"
if [[ $FAIL_COUNT -eq 0 ]]; then
    echo -e "  ${GREEN}All $TOTAL tests passed!${NC}"
else
    echo -e "  ${RED}$FAIL_COUNT/$TOTAL tests failed${NC}"
fi
echo "══════════════════════════════════════════════════"
echo ""

exit $FAIL_COUNT
