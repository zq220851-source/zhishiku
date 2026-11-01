# 第一模块验证记录

本轮在本机独立目录实现并验证；第二模块未改动。测试使用虚构研究、虚构拜访和自然口语，不外发真实员工、医生或患者资料。

## 已执行结果

| 验证层 | 实际命令 | 结果 | 证明范围 |
|---|---|---|---|
| 领域与HTTP | `.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v` | 20/20通过 | 两条流程、原71份课程读取、失败恢复、重复提交、归属隔离、修订撤回、来源校验、历史关联、变式不泄露答案 |
| 浏览器与测试替身 | `.venv/bin/python scripts/browser_check.py` | 通过，页面JS异常0 | 实际点击学习与访前流程、补学重练、刷新恢复、错误重试、修订、HTML按文字显示、历史、390px布局、模拟麦克风离开即关闭 |
| 真实模型 | `.venv/bin/python scripts/live_check.py --config-from 私有配置文件` | 最终4/4通过，无需额外失败重试 | 自然错误→补学→变式正确、否定句、模型选准备重点→试练回填、自填背景不混入C-17 |
| 真实浏览器与真实模型 | `.venv/bin/python scripts/browser_live.py` | 通过 | 页面→HTTP→模型→反馈；访前准备→选择试练→原单更新→刷新恢复 |
| 真实语音服务 | `.venv/bin/python scripts/audio_check.py` | 通过 | 真实TTS产生WAV，真实ASR返回文字，转写不自动提交 |
| 语法 | `python -m py_compile app.py workflow.py knowledge.py models.py`、`node --check web/app.js` | 通过 | Python和浏览器JS语法 |
| 原包完整性 | 按原handoff SHA-256清单逐文件比对 | 263/263一致 | 原源码和数据未被修改 |

真实模型使用已有本机配置中的deepseek-v4-pro；密钥仅在进程内存，没有写入报告。凭证路径不是业务依赖，换机器需配置自己的模型。

## 初次失败与修正

1. 首轮真实学习测试失败，其他3项通过；当时只返回ModelFailure，保留 `live-model-initial-failure.json`。
2. 细查发现两个问题：未观察到行为时模型输出-1索引；准确理解了回答却将原话重新拼接，严格引用校验转为待核实。已改为选择原话编号，程序回填，新增失败回归后修复。
3. 模型生成重练题时有时说出了参考答案。已改为现有课程题目及人工变式，模型不再自由生成重练开场；新增回归后通过。
4. 真实浏览器首次断言等待超时：Playwright的expect默认5秒，并未随页面请求超时一起延长；服务实际已生成反馈。测试等待改为90秒后，端到端通过。保留初次记录，未把它计作通过。
5. 模型测试替身与真实模型结果分开保存，不能用前者证明语义准确性。真实语义验证用原先独立写出的预期，不从模型输出反推预期。

## 证据位置

- `test-results/automated.log`
- `test-results/browser.json`、`browser-live.json`
- `test-results/live-model.json`、`live-generation.json`
- `test-results/audio.json`
- 桌面和窄屏截图、真实模型页面截图在 `test-results/`。
- 两个完整场景的操作材料在 `docs/TEST_MATERIALS.md`，自然口语输入在 `tests/fixtures/journeys.json`。

## 尚未验证或未实现

- 真人麦克风、嘈杂环境、口音准确率、主观接话延迟和音色体验。语音循环使用合成音频，不冒充真人测试。
- 医学准确性、评分与培训师一致性、长期保持和真实拜访迁移效果。当前医学准确性始终NA。
- 71份课程均可读取，但没有对每门逐一开展真人或真实模型教学验收；完整语义验收集中在虚构证据解读材料。
- 日报/专家检索和第二模块的在线对接、真实员工认证、企业多人部署。
- 未迁移旧包的百炼实时连续语音桥接；当前新流程使用手动录音核对提交和医生朗读。
