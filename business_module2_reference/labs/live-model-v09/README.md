# V0.9 真实模型盲测（独立输入/答案）

这是 **实际调用** V0.8 `compatibleSemanticExtractor` + `stageSemanticEvidence` 的工具，不是关键词规则测试。

## 安全边界
- `inputs.json` 只有 25 条虚构中文复盘；运行器不能读取人工标准答案。
- 模型密钥只从运行环境的 `MODULE2_MODEL_API_KEY` 读取，不写进任何文件、源码、截图或日志。
- 模型产生的所有内容均标记 `UNREVIEWED_PROPOSAL`；测试不会修改长期资产、医学知识库或 Skill。
- 请确保 API Key 通过安全的私有环境配置提供。不要复制到脚本命令行、共享终端、截图或聊天。
- 这把曾在聊天中公开过的密钥，应该先在服务商处吊销并替换。

## 在有网络的 Node 22+ 环境执行

```sh
cd medrep_coach_with_ai_rules/module2
node tools/build-benchmark.cjs
# 在私有的本地环境中配置 MODULE2_MODEL_BASE_URL / MODULE2_MODEL_NAME / MODULE2_MODEL_API_KEY
# 仅限明确批准的纯虚构数据：MODULE2_MODEL_DATA_AUTHORIZED=true
node labs/live-model-v09/run-live.mjs --max=3
python3 labs/live-model-v09/score.py labs/live-model-v09/unreviewed-results.json
# 小样本通后再跑完整 25 条：
node labs/live-model-v09/run-live.mjs --max=25
python3 labs/live-model-v09/score.py labs/live-model-v09/unreviewed-results.json
```

## 分数怎么解释
- 精确比较“是否报告专家现场问过外推”四分类：REPORTED / DENIED / HYPOTHETICAL / UNCERTAIN。
- `falsePositiveExpertQuestions` 代表可能污染专家画像、预测和群体经验的危险误识别。
- `missedExpertQuestions` 代表漏掉实际报告的专家问题。
- 25 条仅是 *synthetic held-out challenge*；不是现实世界模型表现估计。
- 这次评分没有覆盖“答复、反思、改口”多事件准确率，下一轮需另外的人工多维金标准。
- **模型返回正确格式、来源定位通过与语义理解正确是三个独立维度。**

## 不可冒充真实结果
- 未发起 HTTP 调用或全部为错误时不得报告模型准确率。
- 只跑 3 条不能报告全部 25 条通过。
- 研究、审核和任何长期资产更新均需单独运行和授权。
