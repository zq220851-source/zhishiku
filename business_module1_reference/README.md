# MedRep 第一模块：学习、访前准备与演练

当前版本 V2（2026-11-01）。学习：完整阅读课程 → 围绕本课交流 → 段后反馈与原文回看。访前：填写背景并关联课程 → 生成准备单 → 可选练一个重点 → 更新同一张准备单。第二模块没有改动。

## 启动

本机运行（依赖已经安装）：

```sh
.venv/bin/python scripts/start_voice_local.py --port 8791
```

访问 http://127.0.0.1:8791 。页面可以连接模型；未连接时仍可阅读课程。也可显式读取已有私有配置：

```sh
.venv/bin/python scripts/start_voice_local.py --config-from /absolute/path/to/private.env --port 8791
```

本地启动脚本使用runtime下的LiveKit服务程序，仅绑定回环地址，并生成本地凭证。跨机器安装、服务构建与已有LiveKit配置见 [实施说明](docs/IMPLEMENTATION_V2.md)。只使用阅读和文字功能时可运行：

```sh
.venv/bin/python scripts/run_local.py --port 8791
```

## 当前实现

- 原包71份课程的情境、讲解、图示、误区、可选自测和来源完整读取。默认展示真实课程，而非虚构演示。
- 三类图示分别呈现为对照栏、流程列表、概念及关系；正文与演练保存同一版本快照。
- Haystack 3.4.1负责本课中文关键词检索，结果可回到材料段落。当前未启用向量检索。
- 学习任务从课程正文生成具体观察项；对话完成或主动结束后集中反馈，不固定两轮、不每句展示评分。
- 自填访前场景可关联课程；准备重点根据目标和背景生成，并验证背景ID与材料ID。
- FastAPI承担接口，LiveKit Agents负责连续音频。原包语音服务通过非流式适配器接入，用户不逐句录音或提交。
- 本次记录保存在runtime/module1.sqlite；API Key不写入数据库或测试材料。

## 验证

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/browser_v2_check.py
.venv/bin/python scripts/live_v2_check.py --config-from /absolute/path/to/private.env
.venv/bin/python scripts/voice_v2_check.py --real-model --config-from /absolute/path/to/private.env
```

语音检查需先启动本地LiveKit，脚本默认使用仅用于开发测试的devkey配置，或通过本地设置读取生成的凭证。测试材料、结果和限制见 [V2验收记录](docs/VERIFICATION_V2.md)。旧版脚本和报告保留作为历史，不代表当前流程。

## 尚未完成

日报与第二模块尚未在线连接；目前接收自填背景及可选的相关表现输入。原资料未完成医学审核，反馈只是相对于课程的学习建议，医学准确性保持NA。Docling、向量检索未接入；当前原包没有PDF/Word等原始文件。语音采用批处理网关，延迟及真人噪声、口音、停顿、打断体验仍需验收。本机Cookie隔离不等于多人生产认证。
