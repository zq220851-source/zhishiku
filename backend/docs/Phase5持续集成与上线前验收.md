# MedRep Coach｜Phase 5：上线前持续集成与验收说明

版本日期：2026-11-01；仅包含独立账号/权限/数据归属索引平台，不包含 V2 的业务模块和前端。

## 本轮实际改动

1. **修复公网访问路径**：`deploy/Caddyfile.staging` 白名单加入 `/v1/teams/*`，防止飞书工作台用户使用“团队名册”时被网关错误返回 404。该 API 的登录和角色授权仍由 FastAPI 强制执行。
2. **数据库版本一致性**：`platform_core/db.py` 在应用启动时校验 `alembic_version` 等于此发行版本对应的 `0003_legacy_evidence`，否则拒绝启动，防止遗漏数据库迁移继续上线。将来每次增加 Alembic 版本必须同步更新 `EXPECTED_SCHEMA_REVISION`。
3. **公网验收脚本**：`scripts/verify_staging.py` 从 5 项增加到 7 项，新增匿名访问团队名册应得 401、未知 API 路径应得 404；仍会检查 Cookie API 的 `Cache-Control: no-store`。
4. **可在 GitHub 使用的 CI 工作流**：`.github/workflows/backend-ci.yml` 包含 SQLite 单元测试和真正 PostgreSQL 16 集成测试两个任务。GitHub Actions 只在你把工程放到相应仓库并启用工作流后运行，**目前尚未执行 CI**。
5. **PostgreSQL 集成测试**：`tests/test_postgres_acceptance.py` 必须显式使用 `TEST_POSTGRES_URL` 指向专用数据库名 `medrep_ci`，并设置 `MEDREP_ALLOW_TEST_DATABASE=YES` 才会运行；否则跳过或直接拒绝执行。它使用合成账号、模拟飞书授权响应，覆盖迁移、登录、个人数据隔离、记录归属与退出。

## 本地已经做过的检查

```text
pytest -q tests
45 passed, 1 skipped
```

其中 1 项跳过是 PostgreSQL 集成测试。当前工作环境没有 Docker、PostgreSQL 实例和真实云服务，所以不能声明已经验证真实 PostgreSQL、Caddy HTTPS 或云端运行。

此外已经完成：

- Python `compileall` 静态语法检查
- 所有 `scripts/*.sh` 的 `bash -n` 检查
- Docker Compose 与 CI YAML 的语法解析
- 本地 SQLite Alembic 迁移后，实际启动 Uvicorn 并通过 HTTP 测试：`/healthz` 200、`/readyz` 200、未登录 `/v1/auth/me` 401、未登录 `/v1/teams/<uuid>/members` 401、无凭证的 `/v1/internal/records/owner` 403。这是**服务直连**的结果；不是 Caddy 公网网关的验收。

## 如何在 GitHub 启用真实 PostgreSQL CI

1. 将 Phase 5 工程源码放入有 GitHub Actions 权限的私有仓库根目录（不要提交 `.env`、dump、API 密钥、员工数据）；CI 采用**纯合成数据**。
2. 检查 `.github/workflows/backend-ci.yml`：GitHub Actions 的 `postgres` 服务创建一个可丢弃的 `medrep_ci` 数据库，运行迁移和 `tests/test_postgres_acceptance.py`。
3. 在 Pull Request 页面观察 `sqlite-tests` 与 `postgresql-acceptance` 两个任务，只有两个都通过才能把本次发布标记为满足代码级门禁；建议在仓库分支保护中要求两个任务必须通过。
4. 这个工作流**不执行生产部署**，不接入飞书生产应用，也不使用生产密钥。首次推送后仍需检查实际 CI 日志与权限。

### 在你自己的临时 PostgreSQL 中手工运行（仅隔离测试数据库）

请不要使用包含真实员工数据的数据库。先在隔离环境创建名为 `medrep_ci` 的空数据库，然后：

```bash
python -m pip install -r requirements-test.txt
export TEST_POSTGRES_URL='postgresql+psycopg://postgres:<临时测试密码>@127.0.0.1:5432/medrep_ci'
export MEDREP_ALLOW_TEST_DATABASE=YES
pytest -q tests/test_postgres_acceptance.py
```

这段命令**会向指定数据库写入合成测试记录和执行迁移**。只允许执行于明确可丢弃的专用 `medrep_ci`；切勿给生产或正式测试主库使用。

## 真正 Staging 云部署需要做什么

在你名下的云账号下，按上一阶段 `docs/Phase4云端测试部署与验收.md` 部署，要求：

- 有可管理的云主机、测试域名、DNS、HTTPS、Docker Engine/Compose；云防火墙仅开放业务需要的端口，SSH 严格限制；数据库 5432 不对公网开放。
- 以真实、仅服务器端保存的 Feishu 企业应用 ID/Secret 配置 .env，不把密钥发到对话、前端仓库或移动包。
- 构建运行 `docker compose -f compose.yaml -f compose.staging.yaml up -d --build` 后，检查 PostgreSQL 已迁移到最新版本、API 健康状态和 Caddy 自动证书。
- 从外部网络执行 `python scripts/verify_staging.py https://<你的测试域名>`，预期 **7 项 PASS**（公网内部接口隐藏应为 404）。
- 分别验证真实飞书授权码、管理员/普通员工/主管权限、角色变更后的会话撤销、跨员工数据隔离和备份恢复。

以上全部没有云账号/授权时**无法完成**；当前 ZIP 不能视为已经在线运行的系统。

## 与业务模块合并的红线

- `V2` 的真实业务服务（Next.js、FastAPI、Cloudflare Worker）**尚未与平台后端正式接入**；不会因 Phase 5 通过而自动获得业务数据的云端存储。
- 禁止直接删除原有 localhost / 测试 Cookie 限制后开放公网；必须在每个业务 API 读写点校验身份和记录归属。
- Phase 5 的用户状态存储是轻量个人设置，不应存放医学训练原始音频、客户身份信息、AI 对话全文或大体积业务记录。
- 真实飞书 H5/独立 App 应与这个 Cookie API 同源部署，语音功能另做 Android 和 iOS 的权限与稳定性测试。

## 版本更新检查表

- [ ] 新增 Alembic 版本时同步 `platform_core.db.EXPECTED_SCHEMA_REVISION`
- [ ] 新增受保护公网 API 时同步审核 Caddy 白名单与 `verify_staging.py`，并编写鉴权测试
- [ ] SQLite 回归测试通过
- [ ] 实际 PostgreSQL CI 通过
- [ ] 云端私有网络与公网拒绝策略验证
- [ ] 备份恢复演练与真实飞书身份验证
- [ ] 业务模块重新接入后端到端验收
