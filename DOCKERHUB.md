<!-- ============================================================
     Docker Hub 仓库描述（复制粘贴用）
     ① 下面「简介」那行 → 粘贴到 Docker Hub 的 Description 字段
     ② `---` 之后的所有内容 → 粘贴到 Overview / Full description 字段
     ============================================================ -->

企业微信可信 IP 自动更新系统 | GitHub: github.com/gldl137/WeWorkIPHelper

---

定时检测公网 IP 变化，自动登录企业微信管理后台更新应用的可信 IP，自带 Web 管理界面。

**GitHub：https://github.com/gldl137/WeWorkIPHelper**

## 功能

- **可信 IP 自动更新**：公网 IP 变化后自动登录企业微信后台，写入最新 IP
- **登录态检查**：Cookie 失效时自动告警，避免静默失败
- **多应用管理**：一个后台账号可同时维护多个自建应用
- **定时任务**：登录检查、公网 IP 检测支持自定义 Cron
- **群机器人通知**：Webhook 推送更新结果与异常
- **可信域名验证**：独立端口托管验证文件
- **数据本地化**：数据库、密钥、日志都在 data/ 目录

## 安装

```bash
docker run -d --name wework-helper \
  -p 5000:5000 -p 5001:5001 \
  -v /path/to/data:/app/data \
  --restart unless-stopped \
  gldl137/weworkiphelper:1.6
```

安装后访问 `http://<你的IP>:5000` 完成初始化。

- 端口：`5000` 主应用、`5001` 可信域名验证
- `data/` 必须挂载持久化，否则容器重建后配置与密钥会丢失
- unraid 等环境若报 `Permission denied: /app/data/...`，
  加 `--user 99:100`（或 `chown -R 99:100 data`）

## 镜像标签

- `1.6` —— linux/amd64 + linux/arm/v7（多架构，按设备自动选择）
- `1.6-armv7` —— linux/arm/v7
