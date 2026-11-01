# Phase 3｜历史归属导入、会话安全与备份恢复

> 适用范围：MedRep Coach 独立平台后端（Phase 1 + 2 + 3）。这是一个可用于**测试环境**的工程，不代表原 V2 三业务模块或真实飞书已完成上线。

## 本轮实际变化

- Alembic `0003_legacy_evidence`：新增 `platform_import_batches`、`platform_import_evidence`。只保留经审批的“历史记录属于谁”以及审核凭据引用；不储存医学报告正文、患者资料、聊天内容或录音。
- `platform_core/legacy_import.py`：强制预审的 CSV 原子导入。默认 dry-run；`--apply` 必须带**该 CSV 文件当前的完整 SHA-256**；跨租户、禁用员工、重复记录、归属冲突、缺审批证据时失败且不提交部分行。
- 会话安全：`POST /v1/auth/logout-all` 撤销本人所有设备的会话；管理员修改员工角色或停用时同时撤销其全部既有会话；所有 `/v1/*` 响应添加 `Cache-Control: no-store`。
- `scripts/backup_postgres.sh`：先核验 `pg_restore --list` 再记录校验值；`scripts/restore_drill_postgres.sh`：校验 SHA256 后将备份**仅恢复到新建的临时测试数据库**，检查 Alembic 版本及用户表，再自动删除测试库。
- `scripts/preflight.py`：只输出部署配置合格/不合格项目，不回显密钥。不提供外网扫描或真正的系统验收。
- `scripts/legacy_storage_inventory.py`：只读清点磁盘 SQLite 数据库的表名/行数；不是迁移或所有权判断。

## 先运行迁移

```bash
# 在工程根目录，测试可用本地 SQLite；生产建议 Postgres。
export DATABASE_URL='sqlite:///./platform-local.sqlite'
export APP_PUBLIC_ORIGIN='http://localhost:9010'
export COOKIE_SECURE=false
export PLATFORM_TENANT_ID=team-test
alembic upgrade head
pytest -q tests
```

旧 Phase 2 数据库可以直接 `alembic upgrade head`；**不要删除旧数据库重建**。在真实数据库升级前，先离线备份并安排维护窗口。首次运行不会自动创建员工账号，按之前 Phase 1 的 CLI 进行显式开通。

## 历史归属导入：只有经过人工认证的历史记录才能导入

CSV 的固定五列：

```
source_module,object_kind,external_ref,owner_user_id,evidence_ref
coach,session,sess-123,<已经核实的员工UUID>,CHANGE-REVIEW-123
```

必须由授权负责人对照**可信历史业务记录和权限规则**，核对每条 `external_ref` 是否确实存在、`owner_user_id` 是否真正属于该员工。`evidence_ref` 为内部审批工单号或不可逆的文档引用标识，不能是患者姓名、电话、邮箱、处方等敏感信息。**工具仅验证格式和平台账号，不自动证明来源真实，也不改写业务库中的 owner 字段。**

CSV 文件不应入库 Git；尽可能放在受控加密目录，完成导入后按数据保留政策安全销毁临时文件。

1. 管理员在独立可信渠道完成核对，并分配审核工单，例如 `CHANGE-2026-1042`。
2. 使用企业授权账号在平台中开通管理员，获得平台 UUID，而不是把飞书 `open_id` 直接当作 owner UUID。
3. 执行预演：

```bash
python -m platform_core.legacy_import \
  --manifest /secure/reviewed_ownership.csv \
  --approved-by <管理员平台UUID> \
  --approval-reference CHANGE-2026-1042
```

4. 双人复核预演行数、数据库备份和 SHA-256，确认无误后执行：

```bash
python -m platform_core.legacy_import \
  --manifest /secure/reviewed_ownership.csv \
  --approved-by <管理员平台UUID> \
  --approval-reference CHANGE-2026-1042 \
  --apply \
  --confirm-digest <预演打印的64位SHA256>
```

同一份清单再次应用时为无变更返回；若内容或审批标记不同必须重新复核。遇到冲突先修订可信源，不要手工删表覆盖归属。

**重要：** 这只会建立 `platform_record_links` 的归属索引。真正让旧训练/复盘数据在手机端可用，还需要新业务代码对各自业务数据库的写入、读取、删除都做原生 owner 校验，并实现数据转换脚本。索引缺失时不允许绕过业务权限。不能因为本轮工具导入成功就声称旧数据库迁移成功。

## PostgreSQL 备份与恢复演练

确保数据库 Compose 服务正常，并在**已完成 PostgreSQL 迁移的测试环境**先验证以下命令：

```bash
bash scripts/backup_postgres.sh
bash scripts/restore_drill_postgres.sh backup/platform-YYYYMMDDTHHMMSSZ.dump
```

第二个脚本只使用程序生成的 `medrep_drill_*` 临时数据库，完成后自动删除，绝不覆盖现有平台数据库。失败时立即停止；请在可审计的测试环境验证清理是否成功。

**限制与待办：**

- 当前备份文件本身不加密，保存位置必须限制访问、用专门密钥加密后再异地存储；定时任务、告警和保留策略尚需由云平台配置。
- `pg_dump` 不是时间点恢复（PITR），也没有自动跨区灾备。
- 本轮运行环境没有 Docker 和 PostgreSQL 服务，**脚本完成静态语法检查，尚未在真实容器执行恢复演练**。
- 备份脚本只覆盖平台 PostgreSQL，不包含原有三模块各自的 SQLite/其他业务库；这些业务库必须另有备份计划。

## 云端生产发布前的强制项目

- [ ] 在你的云账号下创建私有网络/数据库；数据库 5432 不对公网开放
- [ ] 反向代理开启 HTTPS，保护 `/v1/internal/*`，应用始终校验模块服务密钥
- [ ] 前台采用同源请求和安全 Cookie，不向 JS/App 暴露飞书 Secret、数据库密码、模块服务密钥
- [ ] 生产前运行 `python scripts/preflight.py`，消除所有 FAIL，再做实际网络/权限验证
- [ ] 实际飞书身份验证、禁用员工、越权、过期令牌、语音权限在多端逐一测试
- [ ] 为 Feishu 登录增加针对实际部署拓扑的分布式速率限制，实施密钥轮换、异常告警、管理员审计
- [ ] 原 V2 的本机访问限制、测试角色/ Cookie、全局模型密钥入口全部完成生产替换
- [ ] 完成备份加密、异地保存、定时恢复演练及运维负责人指定
- [ ] 确认业务数据的使用授权、保留期限、医学及个人数据合规要求

即使 `scripts/preflight.py` 全部 PASS，也仅意味着**配置结构**看起来合理；不等于服务可用或通过安全审计。
