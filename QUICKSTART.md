# Quick Start Guide - EPICS PV Live Plotter

## Table of Contents
- [Docker Deployment](#docker-deployment)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Running the Application](#running-the-application)
- [Configuration](#configuration)
- [Usage](#usage)
- [Development](#development)
- [Troubleshooting](#troubleshooting)

## Docker Deployment

The easiest way to run this on a new machine (including a Raspberry Pi) is
with Docker Compose - it builds the frontend and backend and runs both,
with no manual Node/Python setup required.

### Prerequisites
- Docker Engine + the Compose plugin (`docker compose version`)

### Run it
```bash
git clone <this-repo> && cd epics-pv-plotter
docker compose up --build -d
```

The app is served on port 80, and the backend on port 8000.

### Why host networking
`docker-compose.yml` runs both containers with `network_mode: host`. This
is required because EPICS Channel Access discovers PVs via UDP broadcast,
which doesn't reach containers on Docker's default bridge network - host
networking makes the containers see the network exactly like a native
process would. This works on Linux hosts (including Raspberry Pi OS); it
does not work the same way on Docker Desktop for Mac/Windows.

If your IOCs are on a different subnet and broadcast discovery doesn't
reach them, copy `.env.example` to `.env` and set `EPICS_CA_ADDR_LIST`
(and `EPICS_CA_AUTO_ADDR_LIST=NO`) to the IOC addresses directly.

### Persisting configuration
`config.json` (PV aliases, EGUs, thresholds, saved layouts) is bind-mounted
into the backend container, so it persists across rebuilds/restarts and can be
edited directly on the host. It holds user-saved settings, so it is not tracked
by git - create it from the template before the first `docker compose up`
(otherwise Docker creates a directory named `config.json` in its place):
```bash
cp config.example.json config.json
```

### Updating after a code change
```bash
docker compose up --build -d
```

### Updating existing Raspberry Pi installations through beamline relays

Run the native deployment script on each intermediate server, from its current
`~/Documents/epics-pv-plotter` checkout. It copies only `calc/`, `routers/`,
`src/`, and `epics_fastapi_gateway.py` to the existing Pi checkout at
`~/Documents/epics-pv-plotter`, then restarts the existing gateway and
frontend systemd services. It verifies each restarted service is active before
reporting success. It does not use Docker, install dependencies on the Pi, or
overwrite `config.json`.

On each intermediate server, configure SSH key access to its Pi and create a
local inventory with the Pi's hostname and username:
```bash
cd ~/Documents/epics-pv-plotter
cp scripts/beamline-pis.inventory.example scripts/beamline-pis.inventory
```
Edit the tab-separated row for that relay's Pi, then deploy just that beamline:
```bash
bash scripts/deploy-beamline-pis.sh --target BL22
```
Use `--all` only if that intermediate server can reach every Pi in its
inventory. The Pi must have `rsync` installed, and the SSH user must have
passwordless sudo for the systemd restart commands. By default, the script
restarts `epics-ws-gateway.service` and `epics-pv-frontend.service`.

For a Pi serving the production build through nginx, use:
```bash
bash scripts/deploy-beamline-pis.sh --target BL22 \
  --frontend-service none --nginx-frontend
```
This builds the frontend on the relay, publishes it to the existing
`/var/www/epics-pv-plotter` web root, and verifies that both the gateway and
nginx are active. The Pi's SSH user needs passwordless sudo for the `rsync`
publication command. Use `--frontend-service none` without
`--nginx-frontend` only when the frontend is served directly from the deployed
checkout by another mechanism. Repeat on each relay using the latest checkout
there.

## Prerequisites

### Required Software
- **Node.js** >= 20.11 ([Download](https://nodejs.org/))
- **Python** >= 3.11 ([Download](https://www.python.org/))
- **Git** ([Download](https://git-scm.com/))

### Optional
- **EPICS Base** (for testing with caget/caput)
- **GitHub CLI** (`gh`) for easier workflow

### Verify Installation
```bash
node --version    # Should be >= 20.11
npm --version     # Should be >= 10.0
python3 --version # Should be >= 3.11
git --version
