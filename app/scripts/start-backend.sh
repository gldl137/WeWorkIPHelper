#!/usr/bin/env bash
# =============================================================================
# 启动后端 (Flask, 端口 5000; 同时后台线程拉起可信域名验证服务 :5001)
# 依赖缺失时由 pip 自动安装到应用专属目录 (PIP_TARGET_DIR, 默认 /app/pip-packages)。
# 用法:
#   bash scripts/start-backend.sh          # 前台运行, Ctrl+C 退出
#   bash scripts/start-backend.sh -d       # 后台守护运行
# 环境变量: BACKEND_PORT/PORT (默认 5000), VERIFY_PORT (默认 5001), DATA_DIR (默认 app/data)
# =============================================================================
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

DAEMON=0
[ "${1:-}" = "-d" ] && DAEMON=1

if [ -z "$PYTHON_BIN" ]; then
  err "未找到 python3 或 python，请先安装 Python 3.11+。"
  exit 1
fi

# ---- 诊断信息 (便于排查启动失败) ----
log "Python: $($PYTHON_BIN --version 2>&1)"
if [ -f "$BACKEND_DIR/app/main.py" ]; then
  log "后端入口: $BACKEND_DIR/app/main.py"
else
  err "未找到 $BACKEND_DIR/app/main.py，后端入口不存在。"
  exit 1
fi
if [ -d "$BACKEND_DIR/templates" ] && [ -d "$BACKEND_DIR/static" ]; then
  log "前端构建产物: 存在 ($BACKEND_DIR/templates, $BACKEND_DIR/static)"
else
  warn "前端构建产物缺失 ($BACKEND_DIR/templates 或 $BACKEND_DIR/static)，请先运行 bash scripts/build-frontend.sh"
fi

# 依赖缺失时自动安装到应用专属目录 (PIP_TARGET_DIR, 默认 /app/pip-packages)
# 不污染系统 site-packages, 可 -v 映射做持久化
if ! py_deps_ready; then
  mkdir -p "$PIP_TARGET_DIR"
  pip install --target "$PIP_TARGET_DIR" -r "$BACKEND_DIR/requirements.txt" --upgrade -i "$PIP_INDEX_URL" \
    || pyrun -m pip install --target "$PIP_TARGET_DIR" -r "$BACKEND_DIR/requirements.txt" --upgrade -i "$PIP_INDEX_URL" \
    || { err "依赖安装失败，请检查网络或 PIP_INDEX_URL"; exit 1; }
fi

mkdir -p "$DATA_DIR"

# 运行时 PYTHONPATH: 指向 PIP_TARGET_DIR (确保 flask 等依赖能被找到)
RUN_PYTHONPATH="$PIP_TARGET_DIR"

# 以模块方式启动（工作目录 = APP_DIR，保证 backend 可作为包导入）
CMD=("$PYTHON_BIN" "-m" "backend.app.main")

if [ "$DAEMON" -eq 1 ]; then
  mkdir -p "$APP_DIR/.run"
  cd "$APP_DIR"
  if [ -n "$RUN_PYTHONPATH" ]; then
    PYTHONPATH="$RUN_PYTHONPATH" DATA_DIR="$DATA_DIR" PORT="$BACKEND_PORT" VERIFY_PORT="$VERIFY_PORT" \
      "${CMD[@]}" >>"$APP_DIR/.run/backend.log" 2>&1 &
  else
    DATA_DIR="$DATA_DIR" PORT="$BACKEND_PORT" VERIFY_PORT="$VERIFY_PORT" \
      "${CMD[@]}" >>"$APP_DIR/.run/backend.log" 2>&1 &
  fi
  echo $! >"$APP_DIR/.run/backend.pid"
  log "后端已在后台启动 (PID $(cat "$APP_DIR/.run/backend.pid")) -> http://localhost:$BACKEND_PORT"
  log "日志: $APP_DIR/.run/backend.log | 停止: kill \$(cat $APP_DIR/.run/backend.pid)"
else
  cd "$APP_DIR"
  [ -n "$RUN_PYTHONPATH" ] && export PYTHONPATH="$RUN_PYTHONPATH"
  export DATA_DIR="$DATA_DIR" PORT="$BACKEND_PORT" VERIFY_PORT="$VERIFY_PORT"
  log "启动后端 -> http://localhost:$BACKEND_PORT (Ctrl+C 退出)"
  exec "${CMD[@]}"
fi
