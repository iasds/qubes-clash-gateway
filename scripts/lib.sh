#!/bin/bash
# scripts/lib.sh — Shared shell utilities for qubes-clash-gateway
# Source this file at the top of every script: source "$(dirname "$0")/lib.sh"
# Or if running from project root: source scripts/lib.sh

set -euo pipefail

# ── Colors ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ── Error Handling ───────────────────────────────────────────────────────────

# Global error handler — called on any command failure via trap
error_handler() {
    local exit_code=$?
    local line_no=$1
    local command=$2
    echo ""
    echo -e "${RED}Error at line ${line_no}: ${command}${NC}" >&2
    echo "Exit code: ${exit_code}" >&2
    echo "" >&2
    echo "Troubleshooting:" >&2
    echo "  - Check if you're running as root (use sudo)" >&2
    echo "  - Check network connectivity" >&2
    echo "  - Check required tools are installed" >&2
    exit "${exit_code}"
}

trap 'error_handler ${LINENO} "${BASH_COMMAND}"' ERR

# ── Logging ──────────────────────────────────────────────────────────────────

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*" >&2
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*" >&2
}

# ── Prerequisite Checks ─────────────────────────────────────────────────────

# Check running as root; exit with clear message if not
require_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "Must run as root. Use: sudo bash $0"
        exit 1
    fi
}

# Check that a command exists; exit with install hint if missing
require_cmd() {
    local cmd=$1
    local hint=${2:-""}
    if ! command -v "$cmd" &>/dev/null; then
        log_error "Missing required tool: ${cmd}"
        if [[ -n "$hint" ]]; then
            echo "  Install with: ${hint}" >&2
        fi
        exit 1
    fi
}

# Check network connectivity to a URL; exit if unreachable
require_network() {
    local url=${1:-"https://www.google.com"}
    local timeout=${2:-5}
    if ! curl -sf --max-time "$timeout" "$url" &>/dev/null; then
        log_error "No network connectivity (tried ${url})"
        echo "  Check your network connection and try again." >&2
        exit 1
    fi
}

# ── Atomic File Operations ──────────────────────────────────────────────────

# Write to a file atomically (write to temp, then move)
# Usage: atomic_write /path/to/file "content"
atomic_write() {
    local target=$1
    local content=$2
    local tmp
    tmp=$(mktemp "${target}.tmp.XXXXXX")
    echo "$content" > "$tmp"
    mv -f "$tmp" "$target"
}

# Backup a file before modifying (creates .bak with timestamp)
backup_file() {
    local file=$1
    if [[ -f "$file" ]]; then
        local backup="${file}.bak.$(date +%Y%m%d_%H%M%S)"
        cp "$file" "$backup"
        log_info "Backed up ${file} → ${backup}"
    fi
}

# ── Service Helpers ─────────────────────────────────────────────────────────

# Check if a systemd service is active
service_is_active() {
    local service=$1
    systemctl is-active --quiet "$service" 2>/dev/null
}

# Restart a systemd service with error handling
service_restart() {
    local service=$1
    log_info "Restarting ${service}..."
    if ! systemctl restart "$service"; then
        log_error "Failed to restart ${service}"
        systemctl status "$service" --no-pager -l >&2 || true
        exit 1
    fi
    log_info "${service} restarted successfully"
}
