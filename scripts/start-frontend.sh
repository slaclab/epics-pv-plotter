#!/usr/bin/env bash
#
# start-frontend.sh
# Starts the EPICS PV Plotter frontend (Vite dev server).
# Can be run manually for testing, or invoked by systemd.
#

set -e

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$SCRIPT_DIR/package.json" ]]; then
    APP_DIR="$SCRIPT_DIR"
else
    APP_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
fi

export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
if [[ -s "$NVM_DIR/nvm.sh" ]]; then
    # shellcheck disable=SC1091
    source "$NVM_DIR/nvm.sh"
    nvm use v20.11.1 >/dev/null 2>&1 || true
fi

cd "$APP_DIR"

echo "=========================================="
echo " Starting EPICS PV Plotter Frontend"
echo " node: $(which node)  ($(node -v))"
echo " npm : $(which npm)   ($(npm -v))"
echo " cwd : $(pwd)"
echo "=========================================="

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-5175}"
exec npm run dev -- --host "$HOST" --port "$PORT"
