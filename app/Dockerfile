# ============================== WeWorkIPHelper 运行镜像 ==============================
# 支持平台：linux/amd64、linux/arm/v7（arm64 亦可；基础镜像 python:3.12-slim-bookworm
# 官方同时提供这三个架构，构建时由 buildx 自动选择对应架构的基础镜像）
#
# 注意：
#   - data 为运行时宿主机挂载目录，禁止 COPY 进镜像。
#   - 【后端 Python 依赖在构建时打包进镜像】，pip install 到应用专属目录
#     /app/pip-packages (PIP_TARGET_DIR)，不污染系统 site-packages。
#   - 依赖用【多阶段构建】：构建阶段带编译工具（arm/v7 上个别依赖没有预编译 wheel，
#     需要本地编译），运行镜像只拷贝编译好的依赖，不包含 gcc 等工具，体积更小。
#   - 前端构建产物已归位到 backend/static (静态资源) 与 backend/templates (模板)；
#     前端源码在 frontend/，改动后执行 bash scripts/build-frontend.sh 重新构建。

# ============================== 阶段 1：依赖构建 ==============================
# 基础镜像可用 --build-arg BASE_IMAGE=... 覆盖（例如国内加速器地址），
# 便于在无法直连 docker.io 时改用镜像站：BASE_IMAGE=docker.m.daocloud.io/library/python:3.12-slim-bookworm
ARG BASE_IMAGE=python:3.12-slim-bookworm
FROM ${BASE_IMAGE} AS deps

# 使用国内 apt 镜像源
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources && \
    sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources

# 编译工具：arm/v7 上 charset-normalizer / MarkupSafe 等可能没有预编译 wheel，
# 需要从源码编译（纯 Python 依赖不受影响，编译只发生在构建阶段）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 使用国内 pip 镜像源
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/

# 安装依赖到独立目录（运行阶段直接拷贝）
# --retries/--timeout 放宽：arm 平台经 QEMU 模拟，网络与编译都比较慢，避免偶发超时中断
RUN mkdir -p /pip-packages
COPY backend/requirements.txt /requirements.txt
RUN pip install --target=/pip-packages \
    --retries 10 --timeout 60 \
    -r /requirements.txt \
    && rm -rf /root/.cache/pip

# ============================== 阶段 2：运行镜像 ==============================
# 与阶段 1 使用同一基础镜像（同样可被 --build-arg BASE_IMAGE 覆盖）
ARG BASE_IMAGE=python:3.12-slim-bookworm
FROM ${BASE_IMAGE}

# 镜像元数据
LABEL maintainer="gldl137"
LABEL name="weworkiphelper"
LABEL version="1.6"
LABEL description="Enterprise WeChat IP Auto Update System"

# 使用国内 apt 镜像源
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources && \
    sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources

# 安装系统依赖 (时区 + 健康检查工具)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tzdata \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && ln -snf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo "Asia/Shanghai" > /etc/timezone

# 创建非 root 用户
RUN useradd -m -u 1000 appuser

WORKDIR /app

# 拷贝构建阶段装好的依赖（不含 gcc / python3-dev 等构建工具）
COPY --from=deps /pip-packages /app/pip-packages

# 复制应用代码（backend 含后端模块 + 前端构建产物 static/ 与 templates/ + 入口 app/main.py）
COPY backend /app/backend

# 镜像内启动脚本 (仅运行必需, 不含本地测试逻辑)
#   - 将构建时安装的依赖目录加入 PYTHONPATH
#   - 启动 Flask (端口/数据目录等由环境变量控制, 见 backend/configmanager.py)
RUN printf '%s\n' \
    '#!/bin/bash' \
    'set -e' \
    'export PYTHONPATH=/app/pip-packages:${PYTHONPATH:-}' \
    'cd /app' \
    'exec python3 -m backend.app.main' \
    > /app/start.sh && chmod +x /app/start.sh

# 创建数据目录并设置权限（运行时挂载点，不随镜像打包）
RUN mkdir -p /app/data/WW_verify && chown -R appuser:appuser /app/data /app/pip-packages

# 环境变量
ENV DATA_DIR=/app/data
ENV IS_DOCKER=true
ENV PORT=5000
ENV VERIFY_PORT=5001
ENV TZ=Asia/Shanghai

# 切换到非 root 用户
USER appuser

# 暴露端口 (主应用 :5000 + 可信域名验证服务 :5001)
EXPOSE 5000 5001

# 健康检查 (依赖就绪、服务起来后才通)
# 用 /health（无需鉴权）；/api/status 需要 API Key，不能作为探针
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# 启动：依赖已在镜像内 (/app/pip-packages)，直接设置 PYTHONPATH 跑 Flask
CMD ["bash", "/app/start.sh"]
