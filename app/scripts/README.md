# WeWorkIPHelper 运行脚本 (scripts/)

用于 Linux / unraid 环境构建前端、启动本项目的后端（Flask，端口 5000，同时后台线程拉起可信域名验证服务 :5001）。脚本为 bash，请在 Linux/unraid shell 运行。

## 脚本

| 脚本 | 作用 |
|------|------|
| `build-frontend.sh` | 构建前端，输出到 `backend/static`（静态资源）与 `backend/templates`（Jinja 模板） |
| `start-backend.sh`  | 启动后端 Flask（:5000）+ 验证服务（:5001），自动安装依赖到应用专属目录 |

> 说明：本项目前端为 Flask 服务端渲染（Jinja 模板 + 原生 JS），由后端直接托管，
> 因此没有独立的 `start-frontend.sh`（前端改动后重新执行 `build-frontend.sh` 即可）。

## 前端目录与构建

```
frontend/                 # 前端源码
├─ src/js, src/css        # JS / 样式源码
├─ templates/             # Jinja 模板源码
├─ build.mjs              # 构建脚本（Node，零依赖）
└─ package.json           # npm run build
```

构建产物：

| 源 | 产物 |
|----|------|
| `frontend/src/**` | `backend/static/**` |
| `frontend/templates/**` | `backend/templates/**` |

构建同时会把模板里的 `?v=xxx` 替换为构建版本（默认 `yyyyMMddHHmm`，可用 `BUILD_VERSION` 覆盖）以刷新浏览器缓存。

## 依赖自动安装

- **前端**：`build-frontend.sh` 检测 `frontend/node_modules` 不存在时自动 `npm install`（本项目无第三方依赖，通常秒过）。
- **后端**：`start-backend.sh` 检测 `flask` 不可导入时自动安装到**应用专属目录**
  `PIP_TARGET_DIR`（不污染系统 site-packages）：
  - **本地测试**（项目不在 `/app`，如 `Weworkiphelper/app`）：`app/pip-packages`（可见目录，不污染本机 Python）。
  - **构建镜像后运行**（项目在 `/app`）：`/app/pip-packages`。
  - 可用环境变量 `PIP_TARGET_DIR` 覆盖；设为 `""` 则退回 pip 默认系统路径。
  - 容器内可把 `/app/pip-packages` 映射到宿主机做依赖持久化（重启不重装）。

## 使用

```bash
cd /path/to/Weworkiphelper/app

# 1) 构建前端（首次或前端改动后执行）
bash scripts/build-frontend.sh

# 2) 启动后端（首次自动安装依赖）
bash scripts/start-backend.sh            # 前台; 加 -d 后台运行
bash scripts/start-backend.sh -d         # 后台运行，日志见 .run/backend.log
```

后端入口为 `backend/app/main.py`，脚本内部以模块方式启动：
`cd app && python -m backend.app.main`（`backend` 需作为包被导入，故工作目录必须是 `app/`）。

## 环境变量

- `BACKEND_PORT` / `PORT` 默认 5000（后端）
- `VERIFY_PORT` 默认 5001（可信域名验证服务）
- `DATA_DIR` 默认 `app/data`（配置 / 数据库 / 日志，建议 unraid 映射到 appdata 盘）
- `PIP_TARGET_DIR` 本地默认 `app/pip-packages`，容器内默认 `/app/pip-packages`（均可 `-v` 映射持久化）
- `BUILD_VERSION` 前端构建产物版本号（默认构建时间）

## 构建并推送 Docker 镜像

镜像基于 `python:3.12-slim-bookworm`，**后端依赖在构建时就 `pip install` 打包进镜像**
（安装到应用专属目录 `/app/pip-packages`，不污染系统 site-packages）。构建一次后，
依赖永久在镜像内，之后**重启容器或删容器重建都不再重新 pip install**。

```bash
# 在 app/ 目录下（含 Dockerfile）执行；前端需先 build-frontend（产物随仓库提交）
bash build_push.sh                        # 默认 1.6，仅 linux/amd64
bash build_push.sh 1.7                    # 指定版本
ARM=1 bash build_push.sh 1.6              # 同时构建 linux/arm/v7（QEMU 模拟，首次较慢）
```

流程与 SLHub 相同：`docker build` → `docker push` 到 Docker Hub（`gldl137/weworkiphelper:<版本>`）。

**arm/v7 说明（`ARM=1` 时）**

- 跨架构构建由 buildx 完成，但**只构建并加载到本机**；推送仍走 `docker push`（daemon 通路，
  与 SLHub 相同），避开 buildx 容器内 DNS 污染导致的推送超时
- buildx 拉取基础镜像走 `app/.buildx/buildkitd.toml` 里的加速器（脚本自动生成）
- 标签约定：amd64 = `:<版本>`，arm/v7 = `:<版本>-armv7`；脚本最后会尝试把两者合成
  多架构 manifest，成功后 arm 设备直接拉 `:<版本>` 即可自动匹配架构
- 验证：`docker buildx imagetools inspect <镜像名>` 可列出已包含的平台

镜像内目录：

```
/app/backend/     ← 后端代码 + 前端产物 (static/ 与 templates/) + requirements.txt
/app/backend/app/main.py ← 应用入口（python -m backend.app.main）
/app/pip-packages ← 构建时已打包的依赖 (在镜像内, 不映射)
/app/data         ← 运行时挂载的数据目录
```

> 注意：依赖随镜像走，升级 Python 大版本 (3.12→3.13) 或修改 `backend/requirements.txt`
> 后必须重新 `docker build`。`/app/data` 仍建议映射到宿主机做数据持久化。

## 访问地址

- 后端/管理界面：http://localhost:5000
- 可信域名验证服务：http://localhost:5001
- 健康检查：`/api/status`
