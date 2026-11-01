# 主线 B 完整离线闭环 / 模块 A 后续 API 集成

**目的**：在没有外部 API、没有模块 1 的条件下，把五资产长期积累、训练与预测需求、场景缺陷、专家观察、群体模式、方法候选的评估和审核全部做成可运行的 **TEST_ONLY** 引擎。

## 你现在可以验证什么

- 6 次虚构拜访 + 1 次历史修订；只使用已经人工核验的结构化输入，而不是模型输出。
- 员工自述、练习缺项、练习满意与后续再次验证分别处理；不把某一次成绩当长期掌握。
- 原任务候选池、已选训练、训练目录、医学知识检索状态分开判断。
- 专家只积累有来源的单次/重复观察；企业群体分母包括拜访、员工与专家，历史更正会使旧模式降级。
- 新准备的旧/新选题同预算比较，不能读取准备之后才出现的拜访；逐项展示挤掉什么。
- 新方法通过开发/留出对照后仍为候选，需要独立测试许可；有回归则拒绝。
- 输出每个候选引用的证据并冻结审核记录；没有自动更新医学知识、专家人格、正式预测策略的接口。

## 离线运行

从项目根目录：

```bash
npm install
npm run test:b:offline
npm run demo:b:offline
```

离线测试台：`module2/demo/b-evolution/index.html`（双击即可打开；也可直接查看打包的 HTML）。
独立审查：`module2/demo/b-evolution/independent-review.json`；冻结金标准：`module2/review_lab/b-evolution/frozen_gold.json`。

## 将来在允许 API 的环境做主线 A/B 测试

密钥只在服务端环境变量中配置，**不要写入这里的代码或资料**，并轮换曾在聊天中公开过的旧密钥。运行前仍需明确仅发送这 25 条虚构口述的授权：

```bash
cd module2
node tools/build-benchmark.cjs
# 设置 MODULE2_MODEL_BASE_URL / MODULE2_MODEL_NAME / MODULE2_MODEL_API_KEY / MODULE2_MODEL_DATA_AUTHORIZED=true
node labs/live-model-v09/run-live.mjs --max=25
python3 labs/live-model-v09/score.py labs/live-model-v09/unreviewed-results.json
cd ..
node tools/build-b-offline.cjs
node tools/bridge-a-to-b-test.cjs
```

最后一步只有在 **25 条真实模型结果完整、来源一致、通过冻结语义金标准逐例校验后**，才允许把匹配的“专家实际提问”测试记录投射到 B 的模拟分析；所有不匹配/错误状态均隔离。结果在 `module2/labs/live-model-v09/oracle-gated-b-test.json`。

**边界**：这一条桥接仅覆盖 25 条基准中的一个“专家是否问过外推”目标，不等于主线 A 全语义准确、五资产端到端全部通过，也不替代医学审核。真正用任何业务数据之前，还需要定义审核主体、身份、知识和留存制度。
