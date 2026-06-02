#!/bin/bash
# scripts/remote-test.sh — SSH connectivity checker for Qubes VMs
# Usage: bash scripts/remote-test.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

NETVM_HOST="localhost"
NETVM_PORT=2222
APPVM_HOST="localhost"
APPVM_PORT=2223

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║   SSH Connectivity Check                        ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# Check sys-testproxy
echo -n "sys-testproxy (NetVM) port $NETVM_PORT: "
if ssh -o ConnectTimeout=5 -o BatchMode=yes -p "$NETVM_PORT" user@${NETVM_HOST} 'hostname' &>/dev/null; then
    echo -e "${GREEN}✓ CONNECTED${NC}"
else
    echo -e "${RED}✗ FAILED${NC}"
    echo "  Try: qvm-connect-tcp $NETVM_PORT:sys-testproxy:22"
    exit 1
fi

# Check testapp
echo -n "testapp (AppVM) port $APPVM_PORT: "
if ssh -o ConnectTimeout=5 -o BatchMode=yes -p "$APPVM_PORT" user@${APPVM_HOST} 'hostname' &>/dev/null; then
    echo -e "${GREEN}✓ CONNECTED${NC}"
else
    echo -e "${RED}✗ FAILED${NC}"
    echo "  Try: qvm-connect-tcp $APPVM_PORT:testapp:22"
    exit 1
fi

echo ""
log_info "All SSH connections OK"
