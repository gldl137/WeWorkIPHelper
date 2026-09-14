#!/bin/bash
#clearLog=true
#noParity=true
#argumentDescription=请输入要构建推送的版本号
#argumentDefault=1.6

# ====================== 配置部分 ======================
HUB_USER="gldl137"
APP_DIR="/mnt/disk1/Python/Weworkiphelper/app"   # 项目根目录(含 Dockerfile)
IMAGE_NAME="weworkiphelper"
VERSION="${1:-1.6}"                              # 版本号: 插件参数优先, 缺省用默认
BUILDER_NAME="weworkiphelper-builder"            # 跨架构构建用的 buildx 构建器(仅构建, 推送不走它)

# ====================== 校验 ======================
echo "[$(date +"%Y-%m-%d %H:%M:%S")] === 构建推送开始: 版本 $VERSION ==="
echo "[$(date +"%Y-%m-%d %H:%M:%S")] 项目目录: $APP_DIR"

if [ ! -d "$APP_DIR" ]; then
    echo "[$(date +"%Y-%m-%d %H:%M:%S")] [ERROR] 项目目录不存在: $APP_DIR，退出"
    exit 1
fi
if [ ! -f "$APP_DIR/Dockerfile" ]; then
    echo "[$(date +"%Y-%m-%d %H:%M:%S")] [ERROR] $APP_DIR/Dockerfile 不存在，退出"
    exit 1
fi

# 检查是否已登录 DockerHub
if [ ! -f "/root/.docker/config.json" ]; then
    echo "[$(date +"%Y-%m-%d %H:%M:%S")] [ERROR] 尚未登录 DockerHub，请先运行 docker login，退出"
    exit 1
fi

# 检查前端产物 (构建镜像前需先 build-frontend.sh)
# 本项目前端为 Jinja 服务端渲染：入口页在 backend/templates/，静态资源在 backend/static/{js,css}
if [ ! -f "$APP_DIR/backend/templates/index.html" ] || [ ! -f "$APP_DIR/backend/static/js/main.js" ]; then
    echo "[$(date +"%Y-%m-%d %H:%M:%S")] [WARN] 前端产物不完整（backend/templates/*.html 或 backend/static/{js,css}），镜像将缺少前端页面"
    echo "[$(date +"%Y-%m-%d %H:%M:%S")] [WARN] 建议先在本机执行: bash scripts/build-frontend.sh"
fi

# 检查后端入口
if [ ! -f "$APP_DIR/backend/app/main.py" ]; then
    echo "[$(date +"%Y-%m-%d %H:%M:%S")] [WARN] 后端入口 backend/app/main.py 不存在，镜像将无法启动"
fi

# ====================== 执行 ======================
cd "$APP_DIR" || { echo "[ERROR] 无法进入 $APP_DIR"; exit 1; }

# 普通构建/推送走 daemon(默认构建器)，与 SLHub 同一条网络通路
docker buildx use default >/dev/null 2>&1 || true

echo "[$(date +"%Y-%m-%d %H:%M:%S")] 【1】docker build (amd64) -> $HUB_USER/$IMAGE_NAME:$VERSION"
docker build -t "$HUB_USER/$IMAGE_NAME:$VERSION" . || { echo "[ERROR] 构建失败"; exit 1; }

echo "[$(date +"%Y-%m-%d %H:%M:%S")] 【2】docker push (amd64) -> $HUB_USER/$IMAGE_NAME:$VERSION"
docker push "$HUB_USER/$IMAGE_NAME:$VERSION" || { echo "[ERROR] 推送失败"; exit 1; }

# ====================== 可选：arm/v7（ARM=1 时构建） ======================
if [ "${ARM:-0}" != "1" ]; then
    echo ""
    echo "[$(date +"%Y-%m-%d %H:%M:%S")] ✅ 完成: $HUB_USER/$IMAGE_NAME:$VERSION (linux/amd64)"
    echo "  需要同时构建 linux/arm/v7 时运行: ARM=1 bash build_push.sh $VERSION"
    docker images "$HUB_USER/$IMAGE_NAME"
    exit 0
fi

# ---- arm/v7 构建：buildx 只负责“构建并加载到本机”，推送仍用 docker push ----
echo "[$(date +"%Y-%m-%d %H:%M:%S")] 【3】arm/v7: 准备 QEMU(binfmt) 模拟"
if [ ! -e /proc/sys/fs/binfmt_misc/qemu-arm ]; then
    docker run --privileged --rm tonistiigi/binfmt --install arm \
        || { echo "[ERROR] QEMU 安装失败"; exit 1; }
fi

echo "[$(date +"%Y-%m-%d %H:%M:%S")] 【4】arm/v7: 准备 buildx 构建器（含 docker.io 拉取加速器）"
# buildkit 容器的 DNS 与宿主机不同路，直连 docker.io 会被污染，拉基础镜像必须走加速器
CFG_DIR="$APP_DIR/.buildx"
CFG="$CFG_DIR/buildkitd.toml"
mkdir -p "$CFG_DIR"
_mirrors='"https://docker.m.daocloud.io", "https://docker.1ms.run", "https://dockerproxy.net"'
{
    echo '[registry."docker.io"]'
    echo "  mirrors = [$_mirrors]"
    echo ''
    echo '[registry."registry-1.docker.io"]'
    echo "  mirrors = [$_mirrors]"
} > "$CFG"
if ! docker buildx inspect "$BUILDER_NAME" >/dev/null 2>&1; then
    docker buildx create --name "$BUILDER_NAME" --driver docker-container --config "$CFG" --use >/dev/null \
        || { echo "[ERROR] 创建构建器失败，可执行 docker buildx rm $BUILDER_NAME 后重试"; exit 1; }
else
    docker buildx use "$BUILDER_NAME"
fi

echo "[$(date +"%Y-%m-%d %H:%M:%S")] 【5】arm/v7: 构建（QEMU 模拟，首次较慢请耐心等待）并加载到本机"
docker buildx build --platform linux/arm/v7 \
    -t "$HUB_USER/$IMAGE_NAME:${VERSION}-armv7" \
    --load . || { echo "[ERROR] arm/v7 构建失败"; exit 1; }

echo "[$(date +"%Y-%m-%d %H:%M:%S")] 【6】docker push (arm/v7) -> $HUB_USER/$IMAGE_NAME:${VERSION}-armv7"
docker push "$HUB_USER/$IMAGE_NAME:${VERSION}-armv7" || { echo "[ERROR] arm/v7 推送失败"; exit 1; }

echo "[$(date +"%Y-%m-%d %H:%M:%S")] 【7】合成多架构 manifest（失败不影响使用）"
docker buildx imagetools create -t "$HUB_USER/$IMAGE_NAME:$VERSION" \
    "$HUB_USER/$IMAGE_NAME:$VERSION" \
    "$HUB_USER/$IMAGE_NAME:${VERSION}-armv7" \
    || echo "[$(date +"%Y-%m-%d %H:%M:%S")] [WARN] manifest 合成失败（不影响：arm 设备可直接拉 ${VERSION}-armv7 标签）"

# 切回默认构建器，避免影响普通 docker build
docker buildx use default >/dev/null 2>&1 || true

echo ""
echo "[$(date +"%Y-%m-%d %H:%M:%S")] ✅ 完成: $HUB_USER/$IMAGE_NAME:$VERSION (linux/amd64 + linux/arm/v7)"
echo "  拉取: amd64 -> $HUB_USER/$IMAGE_NAME:$VERSION"
echo "        arm  -> $HUB_USER/$IMAGE_NAME:${VERSION}-armv7"
echo "        （若 manifest 合成成功，arm 设备也可直接拉 :$VERSION，自动匹配架构）"
docker images "$HUB_USER/$IMAGE_NAME" | head -5
docker buildx imagetools inspect "$HUB_USER/$IMAGE_NAME:$VERSION" 2>/dev/null || true
