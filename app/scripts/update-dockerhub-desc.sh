#!/bin/bash
# =============================================================================
# 更新 Docker Hub 仓库 gldl137/weworkiphelper 的「简介」与「详情页」
# 在 unraid 上运行，凭据取自本机 /root/.docker/config.json（docker login 保存的），
# 无需手输密码、不写死任何密钥。
#
#   bash /mnt/disk1/Python/Weworkiphelper/app/scripts/update-dockerhub-desc.sh
# =============================================================================
set -u

DH_NS="gldl137"
DH_REPO="weworkiphelper"
CFG="/root/.docker/config.json"

echo "=== 更新 Docker Hub: $DH_NS/$DH_REPO ==="

if [ ! -f "$CFG" ]; then
    echo "[ERROR] 未找到 $CFG，请先执行 docker login"
    exit 1
fi

# ---- 取本机登录凭据（base64 的 user:pass）----
AUTH="$(sed -n 's/.*"auth"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$CFG" | head -1)"
if [ -z "$AUTH" ]; then
    echo "[ERROR] $CFG 中没有 auth 字段（可能用 credsStore 存储），"
    echo "        请改为在 Docker Hub 网页后台手动粘贴描述。"
    exit 1
fi
CRED="$(printf '%s' "$AUTH" | base64 -d 2>/dev/null)"
LOGIN_USER="${CRED%%:*}"
LOGIN_PASS="${CRED#*:}"
echo "使用账号: $LOGIN_USER"

# ---- JSON 字符串转义（反斜杠 / 双引号 / 换行）----
esc() { sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' | sed -e ':a' -e 'N' -e '$!ba' -e 's/\n/\\n/g'; }

# ---- 登录换取 JWT ----
TOKEN="$(curl -s -X POST "https://hub.docker.com/v2/users/login/" \
    -H 'Content-Type: application/json' \
    --data-binary "$(printf '{"username":"%s","password":"%s"}' \
        "$(printf '%s' "$LOGIN_USER" | esc)" \
        "$(printf '%s' "$LOGIN_PASS" | esc)")" \
    | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')"

if [ -z "$TOKEN" ]; then
    echo "[ERROR] 登录 Docker Hub 失败（凭据可能已失效，请重新 docker login）"
    exit 1
fi
echo "登录成功，提交描述中..."

# ---- 简介（一行，搜索结果里显示）----
SHORT_DESC='企业微信可信 IP 自动更新系统 | GitHub: github.com/gldl137/WeWorkIPHelper'

# ---- 详情页（Markdown）----
read -r -d '' FULL_DESC <<'EOF' || true
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
- unraid 等环境若报 `Permission denied: /app/data/...`，加 `--user 99:100`（或 `chown -R 99:100 data`）

## 镜像标签

- `1.6` —— linux/amd64 + linux/arm/v7（多架构，按设备自动选择）
- `1.6-armv7` —— linux/arm/v7
EOF

# ---- 组装请求体并提交 ----
{
    printf '{"description":"'
    printf '%s' "$SHORT_DESC" | esc
    printf '","full_description":"'
    printf '%s' "$FULL_DESC" | esc
    printf '"}'
} > /tmp/dh_desc.json

HTTP="$(curl -s -o /tmp/dh_resp.json -w '%{http_code}' -X PATCH \
    "https://hub.docker.com/v2/repositories/$DH_NS/$DH_REPO/" \
    -H "Authorization: JWT $TOKEN" \
    -H 'Content-Type: application/json' \
    --data-binary @/tmp/dh_desc.json)"

echo "HTTP $HTTP"
if [ "$HTTP" = "200" ] || [ "$HTTP" = "201" ]; then
    echo "[OK] 描述已更新，查看: https://hub.docker.com/r/$DH_NS/$DH_REPO"
    curl -s "https://hub.docker.com/v2/repositories/$DH_NS/$DH_REPO/" \
        | sed -n 's/.*"description":"\([^"]*\)".*/当前简介: \1/p'
else
    echo "[ERROR] 更新失败，响应如下："
    head -c 600 /tmp/dh_resp.json 2>/dev/null
    echo
fi
rm -f /tmp/dh_desc.json /tmp/dh_resp.json
