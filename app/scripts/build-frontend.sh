#!/usr/bin/env bash
# =============================================================================
# 构建前端 -> 输出到 backend/static (静态资源) 与 backend/templates (Jinja 模板)
# 用法: bash scripts/build-frontend.sh
# 环境变量: BUILD_VERSION (自定义产物版本号, 默认构建时间 yyyyMMddHHmm)
# =============================================================================
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

if ! have_cmd node; then
  err "未找到 node，无法构建前端。请先安装 Node.js 18+"
  exit 1
fi

if [ ! -f "$FRONTEND_DIR/package.json" ]; then
  err "未找到 $FRONTEND_DIR/package.json，前端工程不完整。"
  exit 1
fi

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  warn "前端未安装依赖，正在 npm install ..."
  (cd "$FRONTEND_DIR" && npm install --no-audit --no-fund)
fi

log "构建前端 (npm run build -> backend/static + backend/templates) ..."
(cd "$FRONTEND_DIR" && npm run build)
log "前端构建完成 ✅ -> $BACKEND_DIR/static, $BACKEND_DIR/templates"
