#!/usr/bin/env bash
# =============================================================================
# WeWorkIPHelper 公共函数库 (被 start-backend.sh 引用)
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$APP_DIR/backend"
FRONTEND_DIR="$APP_DIR/frontend"
DATA_DIR="${DATA_DIR:-$APP_DIR/data}"

# 后端 Python 依赖安装目录 (应用专属, 不碰系统 site-packages)
#   - 容器内 (项目在 /app): /app/pip-packages  (可 -v 映射到宿主机做持久化)
#   - 本地测试 (项目不在 /app): app/pip-packages (可见目录, 不污染本机 Python)
# 可用环境变量 PIP_TARGET_DIR 覆盖; 设为 "" 则退回 pip 默认系统路径
if [ -n "${PIP_TARGET_DIR:-}" ]; then
  PIP_TARGET_DIR="$PIP_TARGET_DIR"
elif [ "$APP_DIR" = "/app" ]; then
  PIP_TARGET_DIR="/app/pip-packages"
else
  PIP_TARGET_DIR="$APP_DIR/pip-packages"
fi

BACKEND_PORT="${BACKEND_PORT:-${PORT:-5000}}"
VERIFY_PORT="${VERIFY_PORT:-5001}"

# pip 镜像源 (国内环境直连官方 pypi 易超时, 默认用阿里云; 可用环境变量覆盖)
PIP_INDEX_URL="${PIP_INDEX_URL:-https://mirrors.aliyun.com/pypi/simple/}"

have_cmd() { command -v "$1" >/dev/null 2>&1; }
log()  { echo "[WeWorkIPHelper] $*"; }
warn() { echo "[WARN] $*" >&2; }
err()  { echo "[ERROR] $*" >&2; }

# 探测 Python 解释器: 优先 python3, 否则 python (兼容 unraid 仅装 python 的情况)
PYTHON_BIN=""
if have_cmd python3; then
  PYTHON_BIN="python3"
elif have_cmd python; then
  PYTHON_BIN="python"
fi
pyrun() { "$PYTHON_BIN" "$@"; }

# 判断关键依赖 (flask) 是否已安装 (在 PIP_TARGET_DIR 或系统路径中均可)
py_deps_ready() {
  local py_path=""
  if [ -n "$PIP_TARGET_DIR" ]; then
    py_path="$PIP_TARGET_DIR"
  fi
  if [ -n "$py_path" ]; then
    PYTHONPATH="$py_path" pyrun -c "import flask" 2>/dev/null
  else
    pyrun -c "import flask" 2>/dev/null
  fi
}
