#!/usr/bin/env bash
# install.sh — One-command setup for pi-lcd-stats on any Raspberry Pi
#
# Usage:
#   git clone https://github.com/gaiar/pi-lcd-stats.git
#   cd pi-lcd-stats
#   ./install.sh
#
set -euo pipefail

SERVICE_NAME="pi-lcd-stats"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
CURRENT_USER="$(whoami)"

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $*"; exit 1; }

# --- Preflight checks ---
echo ""
echo "==============================="
echo "  Pi LCD Stats — Installer"
echo "==============================="
echo ""

# Must be on a Raspberry Pi
if [ ! -f /proc/device-tree/model ]; then
    fail "This does not appear to be a Raspberry Pi."
fi
PI_MODEL=$(tr -d '\0' < /proc/device-tree/model)
info "Detected: ${PI_MODEL}"

# Must have sudo
if ! sudo -n true 2>/dev/null; then
    info "sudo access required — you may be prompted for your password."
fi

# --- Step 1: Enable SPI ---
echo ""
info "Step 1/5 — Checking SPI..."

NEEDS_REBOOT=0
CONFIG_FILE=""
for f in /boot/firmware/config.txt /boot/config.txt; do
    [ -f "$f" ] && CONFIG_FILE="$f" && break
done

if [ -z "$CONFIG_FILE" ]; then
    fail "Cannot find Raspberry Pi config.txt"
fi

if grep -q "^dtparam=spi=on" "$CONFIG_FILE"; then
    ok "SPI already enabled."
else
    if grep -q "^#dtparam=spi=on" "$CONFIG_FILE"; then
        sudo sed -i 's/^#dtparam=spi=on/dtparam=spi=on/' "$CONFIG_FILE"
    else
        echo "dtparam=spi=on" | sudo tee -a "$CONFIG_FILE" > /dev/null
    fi
    ok "SPI enabled in ${CONFIG_FILE}."
    NEEDS_REBOOT=1
fi

# --- Step 2: User groups ---
echo ""
info "Step 2/5 — Checking user groups..."

GROUPS_NEEDED=(spi gpio i2c)
GROUPS_ADDED=0
for grp in "${GROUPS_NEEDED[@]}"; do
    if getent group "$grp" > /dev/null 2>&1; then
        if ! id -nG "$CURRENT_USER" | grep -qw "$grp"; then
            sudo usermod -aG "$grp" "$CURRENT_USER"
            ok "Added ${CURRENT_USER} to group: ${grp}"
            GROUPS_ADDED=1
        fi
    fi
done

if [ "$GROUPS_ADDED" -eq 0 ]; then
    ok "User ${CURRENT_USER} already in required groups."
fi

# --- Step 3: System packages ---
echo ""
info "Step 3/5 — Installing system packages..."

PACKAGES=(
    python3-pil
    python3-psutil
    python3-numpy
    python3-venv
    python3-spidev
    python3-lgpio
    fonts-dejavu-core
    wireless-tools    # provides iwgetid, iwconfig
)

sudo apt-get update -qq
sudo apt-get install -y -qq "${PACKAGES[@]}"
ok "System packages installed."

# --- Step 4: Python venv ---
echo ""
info "Step 4/5 — Setting up Python virtual environment..."

if [ -d "${PROJECT_DIR}/.venv" ]; then
    ok "venv already exists."
else
    python3 -m venv --system-site-packages "${PROJECT_DIR}/.venv"
    ok "venv created at ${PROJECT_DIR}/.venv"
fi

# Verify critical imports
if ! "${PROJECT_DIR}/.venv/bin/python" -c "import spidev, lgpio, psutil, PIL, numpy" 2>/dev/null; then
    fail "Python import check failed — ensure system packages installed correctly."
fi
ok "All Python imports verified."

# --- Step 5: systemd service ---
echo ""
info "Step 5/5 — Installing systemd service..."

# Generate service file from template
sed \
    -e "s|__USER__|${CURRENT_USER}|g" \
    -e "s|__PROJECT_DIR__|${PROJECT_DIR}|g" \
    "${PROJECT_DIR}/pi-lcd-stats.service" \
    | sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null

sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}.service
ok "Service installed and enabled."

# Start unless reboot needed
if [ "$NEEDS_REBOOT" -eq 1 ]; then
    warn "Reboot required for SPI. Service will start automatically after reboot."
else
    if [ -e /dev/spidev0.0 ]; then
        sudo systemctl restart ${SERVICE_NAME}.service
        sleep 2
        if sudo systemctl is-active --quiet ${SERVICE_NAME}.service; then
            ok "Service is running!"
        else
            warn "Service started but may have exited — check: journalctl -u ${SERVICE_NAME}"
        fi
    else
        warn "SPI device not found — service will start after reboot."
        NEEDS_REBOOT=1
    fi
fi

# --- Done ---
echo ""
echo "==============================="
echo "  Installation complete!"
echo "==============================="
echo ""
echo "  Manage the service:"
echo "    sudo systemctl status  ${SERVICE_NAME}"
echo "    sudo systemctl stop    ${SERVICE_NAME}"
echo "    sudo systemctl restart ${SERVICE_NAME}"
echo "    journalctl -u ${SERVICE_NAME} -f"
echo ""

if [ "$NEEDS_REBOOT" -eq 1 ]; then
    echo -e "  ${YELLOW}>>> Reboot required: sudo reboot <<<${NC}"
    echo ""
fi
