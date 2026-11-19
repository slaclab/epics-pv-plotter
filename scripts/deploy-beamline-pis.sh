#!/usr/bin/env bash
#
# Copy the application source to existing Pi installations from a beamline relay.

set -uo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
INVENTORY="$SCRIPT_DIR/beamline-pis.inventory"
GATEWAY_SERVICE="epics-ws-gateway.service"
FRONTEND_SERVICE="epics-pv-frontend.service"
NGINX_FRONTEND=0
DEPLOY_ALL=0
declare -a SELECTED_BEAMLINES=()

usage() {
    cat <<'EOF'
Usage:
  scripts/deploy-beamline-pis.sh --target BEAMLINE [--target BEAMLINE ...]
  scripts/deploy-beamline-pis.sh --all

Options:
  --inventory FILE          Tab-separated beamline, Pi host, Pi user
                            (default: scripts/beamline-pis.inventory)
  --gateway-service NAME   Gateway systemd unit to restart
                            (default: epics-ws-gateway.service)
  --frontend-service NAME  Frontend systemd unit to restart, or "none"
                            (default: epics-pv-frontend.service)
  --nginx-frontend          Build and publish dist/ to nginx's web root;
                            use with --frontend-service none
  --target NAME             Deploy to one beamline; may be repeated
  --all                     Deploy to every beamline in the inventory
  -h, --help                Show this help

Run on the intermediate server that has the current repository checkout and
can SSH directly to its Pi(s). Only calc/, routers/, src/, and
epics_fastapi_gateway.py are copied into ~/Documents/epics-pv-plotter.
EOF
}

fail() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

while (($#)); do
    case "$1" in
        --inventory)
            (($# >= 2)) || fail "--inventory requires a file"
            INVENTORY="$2"
            shift 2
            ;;
        --gateway-service)
            (($# >= 2)) || fail "--gateway-service requires a unit name"
            GATEWAY_SERVICE="$2"
            shift 2
            ;;
        --frontend-service)
            (($# >= 2)) || fail "--frontend-service requires a unit name"
            FRONTEND_SERVICE="$2"
            shift 2
            ;;
        --nginx-frontend)
            NGINX_FRONTEND=1
            shift
            ;;
        --target)
            (($# >= 2)) || fail "--target requires a beamline name"
            SELECTED_BEAMLINES+=("$2")
            shift 2
            ;;
        --all)
            DEPLOY_ALL=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            fail "unknown option: $1"
            ;;
    esac
done

[[ -f "$INVENTORY" ]] || fail "inventory not found: $INVENTORY (copy scripts/beamline-pis.inventory.example)"
[[ "$GATEWAY_SERVICE" =~ ^[A-Za-z0-9_.@:-]+$ ]] || fail "invalid gateway service name"
[[ "$FRONTEND_SERVICE" == "none" || "$FRONTEND_SERVICE" =~ ^[A-Za-z0-9_.@:-]+$ ]] ||
    fail "invalid frontend service name"
if ((NGINX_FRONTEND == 1)) && [[ "$FRONTEND_SERVICE" != "none" ]]; then
    fail "--nginx-frontend requires --frontend-service none"
fi
if ((DEPLOY_ALL == 1 && ${#SELECTED_BEAMLINES[@]} > 0)); then
    fail "use either --all or --target, not both"
fi
if ((DEPLOY_ALL == 0 && ${#SELECTED_BEAMLINES[@]} == 0)); then
    fail "select at least one beamline with --target or use --all"
fi

command -v ssh >/dev/null || fail "ssh is required on the intermediate server"
command -v rsync >/dev/null || fail "rsync is required on the intermediate server"
for path in calc routers src; do
    [[ -d "$REPO_DIR/$path" ]] || fail "missing source directory: $REPO_DIR/$path"
done
[[ -f "$REPO_DIR/epics_fastapi_gateway.py" ]] ||
    fail "missing source file: $REPO_DIR/epics_fastapi_gateway.py"
if ((NGINX_FRONTEND == 1)); then
    command -v npm >/dev/null || fail "npm is required to build the nginx frontend"
    printf 'Building frontend for nginx...\n'
    npm --prefix "$REPO_DIR" run build || fail "frontend build failed"
    [[ -d "$REPO_DIR/dist" ]] || fail "frontend build did not create dist/"
fi

declare -a BEAMLINES=() PI_HOSTS=() PI_USERS=()
while IFS=$'\t' read -r beamline pi_host pi_user extra || [[ -n "${beamline:-}${pi_host:-}${pi_user:-}${extra:-}" ]]; do
    [[ -z "${beamline:-}" || "$beamline" == \#* ]] && continue
    [[ -n "${pi_host:-}" && -n "${pi_user:-}" && -z "${extra:-}" ]] ||
        fail "invalid inventory row for '$beamline'; expected three tab-separated columns"
    [[ "$beamline" =~ ^[A-Za-z0-9._-]+$ ]] || fail "invalid beamline name: $beamline"
    [[ "$pi_host" =~ ^[A-Za-z0-9._:-]+$ ]] || fail "invalid Pi host: $pi_host"
    [[ "$pi_user" =~ ^[A-Za-z0-9._-]+$ ]] || fail "invalid Pi user: $pi_user"
    for existing in "${BEAMLINES[@]}"; do
        [[ "$existing" != "$beamline" ]] || fail "duplicate beamline in inventory: $beamline"
    done
    BEAMLINES+=("$beamline")
    PI_HOSTS+=("$pi_host")
    PI_USERS+=("$pi_user")
done < "$INVENTORY"

((${#BEAMLINES[@]} > 0)) || fail "inventory has no active entries"

declare -a TARGET_INDICES=()
if ((DEPLOY_ALL == 1)); then
    for ((i = 0; i < ${#BEAMLINES[@]}; i++)); do
        TARGET_INDICES+=("$i")
    done
else
    for selected in "${SELECTED_BEAMLINES[@]}"; do
        found=0
        for ((i = 0; i < ${#BEAMLINES[@]}; i++)); do
            if [[ "${BEAMLINES[$i]}" == "$selected" ]]; then
                TARGET_INDICES+=("$i")
                found=1
                break
            fi
        done
        ((found == 1)) || fail "beamline '$selected' is not in $INVENTORY"
    done
fi

SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=15)
RSYNC_RSH="ssh -o BatchMode=yes -o ConnectTimeout=15"
REMOTE_APP_PATH="Documents/epics-pv-plotter"

deploy_one() {
    local index="$1"
    local beamline="${BEAMLINES[$index]}"
    local host="${PI_HOSTS[$index]}"
    local user="${PI_USERS[$index]}"
    local target="${user}@${host}"
    local remote_stage=".epics-pv-plotter-dist-$$-$index"
    local remote_preflight="test -d \"\$HOME/$REMOTE_APP_PATH\" && command -v rsync >/dev/null"

    printf '\nDeploying %s to %s from this relay...\n' "$beamline" "$target"
    if ((NGINX_FRONTEND == 1)); then
        remote_preflight+=" && test -d /var/www/epics-pv-plotter"
    fi
    if ! ssh "${SSH_OPTS[@]}" "$target" "$remote_preflight"; then
        printf 'Preflight failed for %s: check the app directory, rsync, SSH, and nginx web root if applicable\n' "$beamline" >&2
        return 1
    fi

    for path in calc routers src; do
        if ! rsync -a --delete \
            --exclude='__pycache__/' --exclude='*.pyc' \
            -e "$RSYNC_RSH" \
            "$REPO_DIR/$path/" "$target:$REMOTE_APP_PATH/$path/"; then
            printf 'Failed to copy %s/ to %s\n' "$path" "$beamline" >&2
            return 1
        fi
    done

    if ! rsync -a -e "$RSYNC_RSH" \
        "$REPO_DIR/epics_fastapi_gateway.py" \
        "$target:$REMOTE_APP_PATH/epics_fastapi_gateway.py"; then
        printf 'Failed to copy epics_fastapi_gateway.py to %s\n' "$beamline" >&2
        return 1
    fi

    if ((NGINX_FRONTEND == 1)); then
        if ! rsync -a --delete -e "$RSYNC_RSH" \
            "$REPO_DIR/dist/" "$target:$REMOTE_APP_PATH/$remote_stage/"; then
            printf 'Failed to copy frontend build to %s\n' "$beamline" >&2
            return 1
        fi
        if ! ssh "${SSH_OPTS[@]}" "$target" \
            "sudo -n rsync -a --delete -- \"\$HOME/$REMOTE_APP_PATH/$remote_stage/\" /var/www/epics-pv-plotter/"; then
            printf 'Source copied, but nginx frontend publication failed on %s\n' "$beamline" >&2
            return 1
        fi
        if ! ssh "${SSH_OPTS[@]}" "$target" \
            "rm -rf -- \"\$HOME/$REMOTE_APP_PATH/$remote_stage\""; then
            printf 'Frontend published, but staging cleanup failed on %s\n' "$beamline" >&2
            return 1
        fi
    fi

    local -a restart_units=("$GATEWAY_SERVICE")
    if [[ "$FRONTEND_SERVICE" != "none" ]]; then
        restart_units+=("$FRONTEND_SERVICE")
    fi
    local remote_commands=""
    for unit in "${restart_units[@]}"; do
        remote_commands+="sudo -n systemctl restart '$unit' || exit; "
    done
    for unit in "${restart_units[@]}"; do
        remote_commands+="systemctl is-active '$unit' || exit; "
    done
    if ((NGINX_FRONTEND == 1)); then
        remote_commands+="systemctl is-active nginx || exit; "
    fi
    if ! ssh "${SSH_OPTS[@]}" "$target" "$remote_commands"; then
        printf 'Deployment actions completed, but a service health check failed on %s\n' "$beamline" >&2
        return 1
    fi

    printf 'Deployed successfully to %s\n' "$beamline"
}

failures=0
for index in "${TARGET_INDICES[@]}"; do
    if ! deploy_one "$index"; then
        failures=$((failures + 1))
    fi
done

if ((failures > 0)); then
    printf '\nDeployment finished with %d failure(s).\n' "$failures" >&2
    exit 1
fi
printf '\nDeployment completed successfully for %d beamline(s).\n' "${#TARGET_INDICES[@]}"
