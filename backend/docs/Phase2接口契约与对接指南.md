# MedRep Coach Phase 2｜接口契约、集成顺序与权限边界

版本：2026-11-01；基于你已上传的 V2 代码和第一阶段独立平台后端。

## 实际新增内容

1. **团队组织**：`platform_teams`、`platform_team_members`；只有 `admin` 可创建团队和分配人员；`manager` 必须同时是该团队 `lead` 才能查看该团队成员名单。**查看名单不等于有权访问成员训练或复盘数据**。
2. **业务记录归属索引**：`platform_record_links`；保存 `tenant_id + source_module + object_kind + external_ref → owner_user_id`。只存归属元数据，不复制医学内容/录音/模型提示词/患者资料。
3. **可信业务服务凭证**：`COACH_SERVICE_KEY`、`REVIEW_SERVICE_KEY`、`DAILY_SERVICE_KEY` 分别授权对应模块向平台登记记录、查询所有者。一个模块的密钥不能用于另一个模块。未配置时接口默认关闭。
4. **安全调整**：不再支持把浏览器 Cookie 会话令牌当成任意 `Authorization: Bearer` 令牌使用；普通浏览器的写操作继续执行同源校验。
5. **接入 SDK 示例**：`integrations/python/platform_client.py`、`integrations/nextjs/platform-client.ts`。尚未改动你正在优化的三模块业务代码。

## 新增 API

| 请求 | 路径 | 权限 | 说明 |
|---|---|---|---|
| `GET` | `/v1/me/teams` | 已登录 | 自己所属团队，含团队内角色 |
| `POST` | `/v1/admin/teams` | admin + 同源 | 新建团队 |
| `GET` | `/v1/admin/teams` | admin | 公司团队列表 |
| `PUT` | `/v1/admin/teams/{team_id}/members` | admin + 同源 | 新增或更新成员的 `member/lead` |
| `DELETE` | `/v1/admin/teams/{team_id}/members/{user_id}` | admin + 同源 | 移除团队成员 |
| `GET` | `/v1/teams/{team_id}/members` | admin 或该团队 manager+lead | 查看名字/角色，不含训练内容 |
| `GET` | `/v1/me/records?module=coach&limit=30` | 已登录 | 自己的业务记录归属索引 |
| `GET` | `/v1/me/records/{uuid}` | 已登录 | 查看自己的单条归属索引 |
| `POST` | `/v1/internal/records` | 可信模块后台密钥 | 把新业务记录绑定到已启用的员工 |
| `GET` | `/v1/internal/records/owner?object_kind=session&external_ref=s001` | 可信模块后台密钥 | 业务后端查询原记录 owner UUID |

### 内部登记示例（**只允许业务服务端调用**）

请求头：

```text
X-Medrep-Module: coach
X-Medrep-Service-Key: <后端密钥管理中的独立高强度密钥>
```

请求体：

```json
{"owner_user_id":"11111111-1111-4111-8111-111111111111","object_kind":"session","external_ref":"session-001"}
```

注意：`owner_user_id` **必须**来自业务后端成功调用平台 `/v1/auth/me` 后得到的可信会话，绝不能直接取自前端 JSON、URL 参数或普通请求头。系统使用平台配置的租户 ID，不接受客户端自填租户。

相同模块、同一记录、同一 owner 重试是幂等的；如果另一个用户企图占有同一记录，返回 409。新建/查询接口使用模块独立密钥；此密钥必须只保存在后端环境，不能在页面 JavaScript、App 包、日志或飞书前端暴露。

## 不能跳过的业务迁移步骤

1. `medrep_coach_with_ai_rules/`：所有会话相关 **GET/POST/PATCH/DELETE** 必须先验证平台身份，数据库增加可追溯 owner 字段，且每次查询/变更按 owner 过滤。注册归属索引只是第二层防护，**不能代替业务数据库中的 owner 验证**。
2. `module1_source/`：不能直接移除 `127.0.0.1` 限制。先将请求 owner 从随机 `medrep_owner` Cookie 安全迁移为平台用户 UUID，再测试 `Engine` 的所有读写/语音路由。同时把 `/api/credentials` 运行时 API Key 功能迁移为管理员后台或直接禁用，普通员工不可写入全局模型密钥。
3. `module2/`：不能把 `module2_test_session` 测试 Cookie 或 `switchRole` 发布到生产。模块二角色集 `EMPLOYEE/TRAINING_REVIEWER/MEDICAL_REVIEWER/PUBLISHER` 与平台的 `employee/manager/medical_reviewer/admin` **不一一对应**。需要独立能力授权表或严格明示的审批映射，绝不能自动把全局 manager 等同于 TRAINING_REVIEWER 或把 admin 当作所有业务发布权。
4. `medrep-daily/`：消息推送须使用已授权的真实飞书映射，日报已读收藏可逐步接入平台 `state`。医学内容数据、对外通知需经过现有审核与内容安全工作流。
5. 旧数据：三份 SQLite/本地记录的所有者必须通过可信历史证据人工确定。无法确认归属的记录保持隔离，绝不能按员工姓名、当前浏览器 Cookie 或 open_id 猜测归属。

## 数据一致性与重试

当前 Phase 2 的 `platform_record_links` 属于**归属索引**而非业务记录本身。记录写入业务数据库后调用登记接口，发生网络错误可能出现“业务记录已写入但归属索引未登记”的中间状态。正式集成应采用业务库事务 outbox + 后台可靠重试，或者在失败时保持该记录不可访问并进行人工补录；不能因为索引缺失而关闭权限检查。相同 owner 对同一记录登记可安全重试。

## 云端发布安全边界

- `compose.yaml` 的 `platform` 只绑定宿主机 `127.0.0.1:18080`；正式入口必须使用 HTTPS 和正确 DNS。
- **公网反向代理必须拒绝 `/platform/v1/internal/*`**；可参考 `examples/Caddyfile.example`。内部服务路由应位于只对可信后端开放的专用网络，除长密钥之外还应有网络访问控制。
- PostgreSQL 不开放公网 5432，备份独立保存并定期做恢复演练。
- 管理员和成员写接口需要速率限制、访问日志审计以及生产级密钥轮换机制；这些尚未全部实现。

## 仍未完成且不能宣称完成

- 三模块业务 API 真实身份迁移、全部写接口 owner 字段、旧 SQLite 数据迁移；
- 云服务器创建、云数据库实际部署、生产反向代理、HTTPS 域名和自动备份/监控；
- 真实飞书 AppID/Secret 的授权与手机端免登测试；
- LiveKit/AI 语音生产连接、压力测试、医学/个人信息合规检查；
- 生产环境业务角色授权矩阵、完整多租户隔离核验、DPIA/数据保留与删除策略。

本阶段目标是让业务新版能安全、有序接入；不是把 V2 在未修复本机测试机制时直接暴露到公网。
