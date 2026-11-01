# MedRep Coach｜独立后端基础平台 Phase 5

版本：2026-11-01。本包包含 Phase 1–5 **整套平台工程**，与正在优化的 MedRep Coach V2 业务模块分开维护，不覆盖其前后端代码。

## Phase 5 本轮内容

- 修复 Caddy 对团队名册 `/v1/teams/*` 的遗漏，同时保留内部 API 公网隔离。
- API 启动时核对 Alembic 迁移版本，发现数据库升级遗漏会直接阻止启动。
- 公网 HTTPS 安全验收从 5 项扩展到 7 项。
- 新增 PostgreSQL 专用 CI 测试（仅对**可丢弃**的 `medrep_ci` 测试库运行）及 GitHub Actions 双任务工作流。
- 本地测试结果：**45 passed, 1 skipped**（PostgreSQL 没有可用实例，所以跳过）；本地 Uvicorn/SQLite 联调和静态配置检查已通过。

**没有完成真实云端部署、真实 PostgreSQL 测试、飞书授权实测，也没有合并 V2 业务模块。**

详细步骤：`docs/Phase5持续集成与上线前验收.md`。

## 首次本地运行（仅开发环境）

```bash
python -m pip install -r requirements-test.txt
export DATABASE_URL='sqlite:///./platform-local.sqlite'
export APP_PUBLIC_ORIGIN='http://localhost:9010'
export COOKIE_SECURE=false
export PLATFORM_TENANT_ID='team-test'
alembic upgrade head
pytest -q tests
uvicorn platform_core.server:app --host 127.0.0.1 --port 9010
```

如需部署 HTTPS/PostgreSQL 测试环境，参考 `docs/Phase4云端测试部署与验收.md`，并从外网运行 `scripts/verify_staging.py` 做 7 项验收。

## 包的范围

已包含：Feishu 登录后端验证基础、人工开通与禁用员工、角色/团队管理、会话管理、轻量个人状态、只存记录归属的跨模块索引、人工审核的旧记录归属导入、数据库迁移、备份恢复工具、部署配置及测试。

未包含：三个业务模块实际读写迁移、真实员工数据、UI、完整手机 App、完整飞书工作台 H5、云账号与真实密钥。

禁止将此工程当作生产系统直接用于处理真实人员数据，必须先完成真实云端/安全/业务端到端验收。
