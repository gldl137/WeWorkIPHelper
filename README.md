# WeWorkIPHelper · 企业微信可信 IP 自动更新系统

自托管的企业微信（WeCom）可信 IP 维护工具。定时检测公网 IP 变化与登录态，
自动登录企业微信管理后台把最新公网 IP 写入应用的可信 IP 列表，并通过群机器人推送通知。
自带 Web 管理界面，Docker 一键部署。

![Docker](https://img.shields.io/badge/docker-gldl137%2Fweworkiphelper-blue)
![Python](https://img.shields.io/badge/python-3.12-green)
![Platform](https://img.shields.io/badge/platform-linux%2Famd64%20%7C%20linux%2Farm%2Fv7-lightgrey)

---

## 功能特性

- **可信 IP 自动更新**：检测到公网 IP 变化后，自动登录企业微信后台更新指定应用的可信 IP
- **登录态检查与保活**：定时校验 Cookie 是否失效，失效时通过 Webhook 告警，避免静默失败
- **多应用管理**：一个后台账号下可同时维护多个自建应用，按需启用
- **定时任务可配置**：登录状态检查、公网 IP 检测均支持 Cron 表达式，界面内即可调整
- **群机器人通知**：企业微信 Webhook 图文卡片推送更新结果与异常
- **可信域名验证服务**：独立端口提供验证文件托管，供企业微信可信域名校验使用
- **数据完全本地化**：SQLite 数据库、密钥、日志全部落在 `data/` 目录，不依赖任何外部服务
- **多阶段 Docker 构建**：依赖打包进镜像，重启容器无需重新安装；支持 `amd64` 与 `arm/v7`

## 快速开始

### 一、Docker Compose（推荐）

```bash
git clone https://github.com/gldl137/WeWorkIPHelper.git
cd WeWorkIPHelper
docker compose up -d
```

访问 `http://<你的IP>:5000` 进入初始化向导。

### 二、docker run

```bash
docker run -d --name wework-helper \
  -p 5000:5000 -p 5001:5001 \
  -v /path/to/data:/app/data \
  -e TZ=Asia/Shanghai \
  --restart unless-stopped \
  gldl137/weworkiphelper:1.6
```

### 三、本地运行（不使用 Docker）

```bash
cd app
pip install -r backend/requirements.txt
python -m backend.app.main
```

或使用脚本：`bash scripts/start-backend.sh`

## 使用流程

1. 浏览器打开 `http://<你的IP>:5000`
2. **获取并填入企业微信后台 Cookie**（页面上有逐步指引）
3. **添加应用**：填写需要维护可信 IP 的自建应用
4. **配置定时任务与通知**：设置登录检查 / 公网 IP 检测的 Cron、填入群机器人 Webhook
5. **仪表盘**查看登录态、当前公网 IP 与任务执行记录

## 端口与数据

| 端口 | 用途 |
|------|------|
| `5000` | 主应用（Web 界面 + API） |
| `5001` | 可信域名验证服务（可在设置中关闭） |

| 路径 | 内容 |
|------|------|
| `/app/data/database.sqlite` | 数据库（配置、应用、IP 变更历史） |
| `/app/data/secret.key` | 会话密钥（首次启动自动生成） |
| `/app/data/weworkiphelper.log` | 运行日志（10MB 滚动） |
| `/app/data/WW_verify/` | 可信域名验证文件 |

> `data/` 目录**必须挂载持久化**，否则容器重建后配置与密钥会丢失。

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `TZ` | `Asia/Shanghai` | 时区（影响日志与 Cron 执行时间） |
| `PORT` | `5000`（Docker）/ `1110`（本地） | 主应用端口 |
| `VERIFY_PORT` | `5001`（Docker）/ `1109`（本地） | 可信域名验证端口 |
| `HOST` | `0.0.0.0` | 监听地址 |
| `DATA_DIR` | `/app/data`（Docker）/ `./data`（本地） | 数据目录 |
| `IS_DOCKER` | 自动判断 | 运行环境标记 |

## 目录结构

```
app/
├─ backend/                后端（Flask）
│  ├─ app/main.py          应用入口（启动与装配）
│  ├─ routes/              路由：api / pages / frontend
│  ├─ taskscheduler.py     定时任务调度（基于 croniter）
│  ├─ ip_updater.py        企业微信可信 IP 更新
│  ├─ loginchecker.py      登录态检查
│  ├─ publicipfetcher.py   公网 IP 获取
│  ├─ commonutils.py       Webhook 通知等公共逻辑
│  ├─ trusteddomainverify.py 可信域名验证服务
│  ├─ templates/           页面模板（前端构建产物）
│  └─ static/              静态资源（前端构建产物）
├─ frontend/               前端源码（src + templates + build.mjs）
├─ scripts/                本地启动与前端构建脚本
├─ pip-packages/           本地依赖目录（不提交）
├─ data/                   运行时数据（不提交）
├─ Dockerfile              多阶段构建
└─ build_push.sh           构建并推送到 Docker Hub
docker-compose.yml
```

## 构建与发布

后端依赖在**构建时**安装进镜像（`/app/pip-packages`），运行镜像不含编译器，体积更小。

```bash
cd app
bash build_push.sh              # 构建并推送 amd64
ARM=1 bash build_push.sh 1.6    # 额外构建 arm/v7（QEMU 模拟，首次较慢）
```

前端改动后需重新生成产物（`backend/templates` 与 `backend/static`）：

```bash
bash scripts/build-frontend.sh
```

## 常见问题

**Q：容器启动报 `PermissionError: '/app/data/weworkiphelper.log'`？**
挂载目录属主与容器内用户不匹配。unraid 上文件默认属主是 `nobody:users`（99:100），
在 `docker-compose.yml` 中加 `user: "99:100"`，或修正宿主机目录属主：

```bash
chown -R 99:100 /path/to/data        # unraid
# 或改用镜像内默认用户： chown -R 1000:1000 /path/to/data
```

**Q：Cookie 多久失效？**
企业微信后台会话有效期由官方控制，建议保持「登录状态检查」定时任务开启，
失效时会在仪表盘与 Webhook 中告警，重新获取 Cookie 填入即可。

**Q：可信域名验证服务怎么用？**
把企业微信要求的验证文件放入 `data/WW_verify/`，保持 `5001` 端口可被外网访问即可。

## 安全说明

- 项目**不包含**任何账号、Cookie、密钥；所有凭据都由你填写并存储在本地 `data/` 目录
- `data/`、`secret.key`、日志已在 `.gitignore` 中排除，请勿手动提交
- 后台 Cookie 属于敏感凭据，等同于账号登录态，请勿泄露或分享截图

## 免责声明

本项目仅供个人学习与自用，使用前请确认符合企业微信相关的服务条款与所在组织的管理要求。
因使用本工具导致的账号风控、数据丢失等后果由使用者自行承担。

## 致谢

基于 Flask、APScheduler、croniter、Requests 构建。
