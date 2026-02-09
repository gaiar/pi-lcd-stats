#!/usr/bin/env bash
# uninstall.sh — Remove pi-lcd-stats service and clean up
set -euo pipefail

SERVICE_NAME="pi-lcd-stats"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

info() { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()   { echo -e "${GREEN}[OK]${NC}    $*"; }

echo ""
echo "  Pi LCD Stats — Uninstaller"
echo ""

# Stop and disable service
if systemctl list-unit-files "${SERVICE_NAME}.service" &>/dev/null; then
    info "Stopping service..."
    sudo systemctl stop "${SERVICE_NAME}.service" 2>/dev/null || true
    sudo systemctl disable "${SERVICE_NAME}.service" 2>/dev/null || true
    sudo rm -f "/etc/systemd/system/${SERVICE_NAME}.service"
    sudo systemctl daemon-reload
    ok "Service removed."
else
    ok "Service was not installed."
fi

echo ""
echo "  Done. Project files in $(cd "$(dirname "$0")" && pwd) were NOT removed."
echo "  To fully remove:  rm -rf $(cd "$(dirname "$0")" && pwd)"
echo ""
