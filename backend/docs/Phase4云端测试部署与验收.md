# Phase 4 | 云端测试环境（Staging）部署与验收手册

**范围**：仅部署 Phase1–4 的 MedRep Coach 账号/权限/业务归属索引平台 + PostgreSQL。**不包含**原 V2 的 FastAPI 陪练、Next.js 主演练台、复盘模块或 Cloudflare 学术日报工作者，也没有实际云端部署；你仍需提供云平台资源和企业飞书授权。

## 1. 部署前选择

- 建议使用独立于生产的 **Linux 测试云主机**、独立测试域名和测试飞书应用，采用 Docker Engine + Compose v2。服务器地区须根据团队所在国家/地区、数据合规要求及服务商支持情况确定；不要急于购买长期资源。
- 确保能操作域名 DNS，给测试域名配置 A/AAAA 到云主机公网 IP（无 IPv6 时不要设置无效 AAAA）。云防火墙开放入站 TCP 80/443（Caddy 自动 HTTPS 需要）；SSH 22 尽量只允许管理员固定 IP。数据库 PostgreSQL 5432 **绝不对公网开放**。
- 这份工程仍以 `POSTGRES_PASSWORD` 等 `.env` 环境变量运行，生产阶段应迁移到云密钥管理、最小权限与完善审计。

## 2. 将本 ZIP 工程安全放到云主机

Linux 云主机安装 Docker Engine 和 Compose v2，将本工程上传到专用目录，如 `/srv/medrep-platform-staging`；使用专门运维账号，限制 SSH 权限。

在该目录执行（**替换为你有权管理的真实域名**）：

```bash
python3 scripts/init_staging_env.py --domain coach-staging.your-company.cn --tenant-id company-staging
chmod 600 .env
```

此命令生成随机数据库密码，不会打印密钥，也拒绝覆盖已有 `.env`。随后在云主机上以安全方式编辑 `.env`，补入 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET`。**不要发送这些密钥到聊天、GitHub 或任何前端代码。**

准备好飞书企业自建应用后，在后台为测试成员配置权限/应用可用范围，确保测试时只使用测试账号。没有真实飞书配置时，服务器可启动但飞书登录无法工作。

运行配置检查（不打印密钥内容）：

```bash
set -a; source .env; set +a
python3 scripts/preflight.py
```

确认 `APP_DOMAIN` **严格等于** `APP_PUBLIC_ORIGIN` 的域名部分，且数据库与密码一致。任何 `FAIL` 必须先解决。注意 `source .env` 仅适用于本生成器写出的 shell 安全字符值，不要随意 source 不可信配置文件。

## 3. 启动 Staging 后端和 HTTPS

```bash
docker compose -f compose.yaml -f compose.staging.yaml config --quiet
docker compose -f compose.yaml -f compose.staging.yaml up -d --build
docker compose -f compose.yaml -f compose.staging.yaml ps
```

基础 `compose.yaml` 会把平台 API 暴露在宿主机 `127.0.0.1:18080` 供运维检查，但不会向公网监听。Staging 覆盖层新增 Caddy 反向代理开放 **80/443**：Caddy 为正确指向服务器的域名自动获取 HTTPS 证书。必须实际验证 TLS 证书和 DNS 工作正常。

安全边界：Caddy 仅将 `/v1/auth/*`、`/v1/me/*`、`/v1/admin/*`、`/healthz` 转发到平台服务；`/v1/internal/*`、`/readyz` 及其他未知 `/v1/*` 均不会在公网转发。真正的模块间通信只能在可信的私有网络中进行，并须带独立模块服务凭证。**浏览器、飞书 H5 和手机 App 均不能持有服务密钥。**

当前打开 `https://coach-staging.your-company.cn/` 只会得到一个“平台 API 已启动、业务 UI 尚未部署”的提示，不会看到完整的 MedRep Coach 页面。这是预期行为。

## 4. 不需要任何真实账号的公网冒烟测试

从另一台有公网连接的电脑运行：

```bash
python3 scripts/verify_staging.py https://coach-staging.your-company.cn
```

预期：5 项 PASS，分别检测健康接口、未登录信息隔离、未登录记录隔离、内部接口隐藏、数据库就绪接口不对外暴露。工具严格验证 TLS，不使用 `-k` 忽略证书错误。**这不是全业务测试、负载测试、渗透测试或合规验收。**

在云主机内检查容器状态与迁移结果：

```bash
docker compose -f compose.yaml -f compose.staging.yaml ps
docker compose -f compose.yaml -f compose.staging.yaml logs --tail=100 platform
docker compose -f compose.yaml -f compose.staging.yaml exec platform python -m platform_core.cli --help
```

不要在日志或截图中暴露 `.env`、授权码、Cookie、数据库密码及员工信息。

## 5. 飞书管理员开通与账号测试

需要先由组织管理员通过可靠渠道确认该员工的真实飞书 `open_id`，再通过 CLI 明确开通。不要根据用户自己提交的 `open_id` 分配权限。

```bash
docker compose -f compose.yaml -f compose.staging.yaml exec platform python -m platform_core.cli provision \
  --tenant-id company-staging --open-id 'ou_真实且已核验的open_id' --name '测试管理员' --role admin
```

之后需开发并部署同源的飞书 H5 前端，完成真实授权码交换、会话 Cookie、退出登录、跨角色权限测试。这一步不在 Phase 4 交付的服务中，因此**暂时无法仅靠部署这套工程验证真实飞书登录**。

## 6. 数据备份与恢复

**先用测试数据验证**：

```bash
bash scripts/backup_postgres.sh
bash scripts/restore_drill_postgres.sh backup/platform-YYYYMMDDTHHMMSSZ.dump
```

脚本依赖正在运行的 Compose 服务，使用容器内 `pg_dump` / `pg_restore`。备份文件默认是未加密的 PostgreSQL dump，**不能直接作为长期异地备份**；必须加密保存到不同故障域、安排定时备份及失败告警，并定期恢复演练。平台备份**不包含三个业务模块的 SQLite、医学知识数据、上传文件、录音或对象存储**。

旧会话清理：

```bash
docker compose -f compose.yaml -f compose.staging.yaml exec platform python -m scripts.cleanup_sessions
# 审核 dry-run 数量后再实际操作：
docker compose -f compose.yaml -f compose.staging.yaml exec platform python -m scripts.cleanup_sessions --apply
```

## 7. 上线前仍然需要完成

- [ ] 企业云账号、域名、DNS、SSH、Caddy/TLS 实际配置与验收
- [ ] 容器内真实 PostgreSQL 启停、Alembic、备份与恢复演练
- [ ] 真正的飞书 H5 免登授权、真实员工和团队权限实测
- [ ] 登录接口按实际公网拓扑增加可信反向代理/边缘的分布式限流、告警及审计
- [ ] 整合三个 V2 业务模块，特别是模块二测试 Cookie、模块一本机限制、语音鉴权
- [ ] 对所有业务库、附件、录音、医学资料设置分别的安全备份方案
- [ ] 明确药学/员工数据使用范围、权限、留存政策和适用法律的要求
- [ ] 验证飞书内 Android/iOS WebView 麦克风、录音和实时音频

**请勿在本轮没有实际完成的步骤上标记上线成功。**
