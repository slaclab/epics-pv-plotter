#!/usr/bin/env bash
#
# start-frontend.sh
# Starts the EPICS PV Plotter frontend (Vite dev server).
# Can be run manually for testing, or invoked by systemd.
#

set -e   # 出错即退出

# ------------------------------------------------------------
# 1. 加载 nvm（关键：让 node/npm 可用）
# ------------------------------------------------------------
export NVM_DIR="/home/b_bluesky/.nvm"
# shellcheck disable=SC1091
[ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"

# 使用指定的 node 版本（和你 which node 一致）
nvm use v20.11.1 >/dev/null 2>&1 || true

# 兜底：直接把 node bin 目录加进 PATH
export PATH="/home/b_bluesky/.nvm/versions/node/v20.11.1/bin:$PATH"

# ------------------------------------------------------------
# 2. 进入项目目录
# ------------------------------------------------------------
cd /home/b_bluesky/Documents/epics-pv-plotter

# ------------------------------------------------------------
# 3. 打印环境信息（方便调试）
# ------------------------------------------------------------
echo "=========================================="
echo " Starting EPICS PV Plotter Frontend"
echo " node: $(which node)  ($(node -v))"
echo " npm : $(which npm)   ($(npm -v))"
echo " cwd : $(pwd)"
echo "=========================================="

# ------------------------------------------------------------
# 4. 启动 Vite dev server
#    exec 让 npm 进程替换当前 shell，便于 systemd 正确管理进程
# ------------------------------------------------------------
exec npm run dev -- --host 0.0.0.0 --port 5173
