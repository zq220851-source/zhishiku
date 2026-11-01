> 私用配置版：本包按用户要求包含服务 API Key（.env.local）。请勿公开上传或分享；历史验收文档中“不含密钥”描述指无密钥源码版。

# MedRep Coach · 原版 UI 恢复与功能接续开发版

本版从 2026-11-01 交接包的修复中源码继续开发，保留登录页，复用原版 3D 角色、开屏与玻璃样式，并修复三模块接线。**这是可本机体验的开发版，不是全部业务或企业部署已验收的发行版。** 当前状态见 [本轮实现与验收](docs/06_本轮实现与验收.md)。

## 本机启动

需要 Node.js 24、Python 3.11 或更新版本。首次运行：

```sh
python3 scripts/setup_local.py
# 此私用包已包含 .env.local 和 API Key，请保留现有配置
python3 scripts/run_local.py
```

打开 http://localhost:5190/ 。首次启动自动生成本机测试账号，见项目根目录 `本机体验说明.txt`；密码、密钥和运行数据不包含在源码交付包中。`.env.local` 仅在服务端使用，勿填入前端 VITE 配置。Ctrl-C 关闭本次启动的五个服务。

- 平台 9011；模块一 8791；模块二 3402；模块三 8887，均绑定本机。
- H5 使用同源代理连接平台和实时 WebSocket。
- 原版完整 3D 已在 Chrome 检查；内置浏览器初始化失败时显示明确的备用状态。
- 课程表达和访前模拟使用连续语音；背景输入、课程阅读及复盘转写核对保留文字。
- 课程和临床知识资产来自交接包，来源状态仍为待审核。

## 验证

```sh
backend/.venv/bin/python scripts/check_providers.py
backend/.venv/bin/python scripts/check_previsit_flow.py
python3 scripts/smoke_local.py
```

真实服务检查会调用已配置供应商。`check_voice_flow.py` 使用 `runtime/live-run.json` 中的本机练习，发送合成 PCM；它不录制麦克风，也不等于真人语音体验验收。`check_review_flow.py` 使用同一测试任务，明确创建模拟复盘。

回归测试分别在子目录运行：backend 的 `python -m pytest -q`，模块一的 `python -m unittest discover -s tests`，模块二的 `npm test`，模块三的 `npm test`，mobile_app 的 `npm run test:contract`。Python 测试请使用对应 `.venv/bin/python`。

## 团队共享场景与选题策略

复盘页的“团队共享场景与选题策略 · L2 / L3”入口读取真实团队范围。L2 复用原资料场景；L3 在固定预算中调整已知候选优先级。本人提出候选后，另一位有职责的团队审核人选取两份独立实际交流（验证／留出），核验原文、标准及资料版本，再批准团队训练共享。来源变化或撤回后停止新使用。

准备页可以显式选用已审核版本、设置预算并比较基础方案与共享建议；仍需本人确认冻结。当前体验账户没有真实团队和合格实际交流，因此共享列表为空。完整协议测试使用隔离数据库，未写入业务数据。

## 部署范围

本轮没有推送仓库、公开源码或发布飞书。历史部署文档仍保留在 `docs/`，其完成状态不覆盖本轮验收记录。企业身份、审核职责、真实专家身份与群体数据需要实际接入；本机体验账号不代表这些接入已完成。
