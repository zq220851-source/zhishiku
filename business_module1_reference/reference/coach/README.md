> **交接版本：2026-11-01。请先阅读 [最新开发交接说明](先读我-开发交接.txt)，启动方式及当前默认设置以交接说明和代码为准。下方保留历史记录。**

## 2026-10-31 方案①：百炼流式语音（8775，待真实凭证验收）

新增 `voice-demo/realtime_voice.py` 与 `realtime-voice.js`。启动 `../.venv/bin/python server.py --port 8775` 后，HTTP 页面使用 8775，WebSocket 桥接使用 8776，均仅绑定 127.0.0.1。配置面板接收百炼地域、Workspace ID、API Key，仅在内存保存，通过两种模型的 `session.updated` 后才启用模式；这仅是连接/会话配置验证，不是识别和音频内容验收。

ASR：qwen3-asr-flash-realtime，麦克风 AudioWorklet 分块采集并转为 16k PCM，持续上传，显示可修订草稿，仅 completed 原文提交 DeepSeek。保留 1.2/5 秒服务端 VAD 选项；每次完整发言后关闭识别连接，医生说完再建立连接；暂不支持全双工打断。失败音频暂存在页面内存，最多约两分钟，可人工触发 Credits 原主备方式重试。

TTS：qwen3-tts-flash-realtime，现有医生首句生成后按句提交文本，音频增量直接经 WebSocket 到 AudioContext 排程播放，不再等完整 WAV。仍以完整句子为输入单位，尚未把 LLM 每个 token 连续送入同一长期连接。Maia/Andre 保留；实际声音须重新试听。客户端等待音频播放结束再恢复收音，结束/取消会关闭连接和清空已排程音频。

医生和评分仍用现有 Credits DeepSeek。新增流式连接校验 Origin、会话有效期、可朗读的已登记医生文本；API Key 不出现在 WebSocket URL、localStorage、输出日志或配置查询中。总计 34 项 Python、33 项 JS 自动化检查通过，新增协议测试使用模拟百炼端；不能据此声称真实延迟已改善。当前未配置百炼凭证，真实端到端验收待完成。

协议依据：
- https://help.aliyun.com/en/model-studio/qwen-asr-realtime-client-events
- https://help.aliyun.com/en/model-studio/qwen-asr-realtime-server-events
- https://help.aliyun.com/en/model-studio/qwen-tts-realtime-client-events
- https://help.aliyun.com/en/model-studio/qwen-tts-realtime-server-events

## 2026-10-31 转写等待与容错更新（8774）

使用 `voice-demo/requirements-voice.txt` 安装依赖。新增 aiohttp 为转写连接提供覆盖连接、响应头、完整响应体的可取消总时限。

自动模式先请求 Whisper；5 秒仍未完成时，保留主请求并启动一次 Qwen 备用。可回退的立即错误会提前启动备用；身份验证/参数错误不重试。采用先完成的完整转写，并取消另一条本机 HTTP 请求（上游已开始处理的计费不保证取消）。两路仍共用 Credits，因此不能消除共用网关故障；慢请求可能产生双份额度消耗。

主备总等待上限 25 秒；前端等待上限 28 秒，失败仍可重试页面内存里的录音。自动模式不混合两路部分文本，只提交胜出的完整结果。Whisper 429 后冷却 20 秒。保留单独 Whisper/Qwen 选项。新策略尚需真人麦克风环境验证，固定录音测试不代表识别准确率。

保持 1.2 秒默认接话间隔及 5 秒选项；保持 Maia/Andre、按句预取播放、六维评分与计时功能。Qwen 音频分块实测首块后仅约 0.32–0.97 秒便收完，因此本轮未改为自定义 PCM 流播放。

运行：`../.venv/bin/python server.py --port 8774`（在 voice-demo 下，密钥通过既有环境变量配置）。

# MedRep Coach 端到端原型

新增：面向药代—医生模拟对话的[可溯源候选评分标准](scorecards/README.md)及项目内 Skill `.agents/skills/medrep-dialogue-scorecard/`。四本用户提供的书籍、信达官方营销与道德政策已索引入临床 SQLite 的候选资料表；该版本不含未经校准的总分或权重，正式评价前需培训、医学及合规审核。

新增试用版：[医院拜访语音演练](voice-demo/README.md)。默认选择 OpenAI Next Credits 平台列表中的国产模型 `deepseek-v4.1-flash`；按语音演练说明安装 `edge-tts` 并运行 `.venv/bin/python voice-demo/server.py --port 8767`，在浏览器打开 `http://127.0.0.1:8767`，可直接在页面输入并验证完整的 Credits API Key；支持 5/10 分钟与自定义计时、Qwen API 连续语音转写、可选普通话音色、按日报负责管线匹配场景、API 生成的自然多轮对话及带雷达图的六维机器初评。未连通 API 时不进入模拟会话。

> 目标：把整条链路跑通，看到全貌。
> 这不是完整实现，是**最小可验证闭环**——每个环节都能跑、能看输出、逻辑正确。

---

## 一、跑通的链路

对应 V1.3 §4.1 的数据流 A：

```
VisitContext（医生画像卡）
   ↓
QuestionCandidate（候选考点，带可解释优先级）
   ↓
PredictionPlan（训练计划，题量可配）
   ↓
SimulationSession（AI 医生多轮追问）
   ↓
DualAssessment（两轨 9 维 + 4 闸门 + 降档表）
   ↓
ErrorEvent（错误留存，可聚合）
   ↓
EmployeeSkillState（GAP 画像，可行动诊断）
   ↓
AssessmentReport（训练报告）
```

**全部离线运行，零外部 API 依赖。**

---

## 一之二、快速开始

```bash
# 1. 看环境（自动探测项目根目录，检查依赖是否齐全）
make env

# 2. 配置 API key（可选用 secret 工具管理，不落盘）
export MINIMAX_API_KEY=sk-cp-你的key
#   或：cp .env.example .env && 编辑后 source .env

# 3. 跑全部自检（8 套）
make check

# 4. 看端到端演示（8 场景，含真实 LLM）
make demo

# 5. 看复盘链路演示
make feedback

# 6. 跑一次训练
make train                    # 规则引擎
make llm                      # 真实 LLM
```

### 交付包与构建

```bash
make pack       # 构建原型包
```

打包脚本 `build_prototype_pack.py` 做三件事，**不靠手写文件列表**：

| 步骤 | 内容 |
|---|---|
| ① 全量同步 | 按目录/通配符同步，不逐文件列举（手写列表会漏文件）|
| ② 内容校验 | 逐文件比对包内与源目录的 md5 |
| ③ **独立可运行性验证** | 解压到**随机临时目录** + **清空环境变量** + **不带 API key**，跑全部自检 |

③ 是关键：它验证包**不依赖 `/workspace/output`**。

> **踩过的坑**：早期用手写文件列表打包，漏了 5 个文件，
> 包里留的是旧版（硬编码 `BASE = "/workspace/output"`）——
> 换台机器就指向不存在的路径，**而且不报错**，只是静默行为异常。
> 所以现在：全量同步 + md5 校验 + 独立运行验证，三道关。

### 配置说明

所有路径与运行参数集中在 `config.py` + `config.json`：

| 位置 | 管什么 |
|---|---|
| `config.py` | 路径（自动探测）、默认参数、环境自检 |
| `config.json` | LLM provider / 模型名 / 端点 / 温度（改这个不用改代码）|
| 环境变量 | `MEDREP_BASE`（项目根）、`MEDREP_LLM_PROVIDER`、`MEDREP_LLM_MODEL`、`MEDREP_TEMPERATURE` |

**优先级**：环境变量 > config.json > 代码默认值。

`config.py` 会自动探测项目根目录（找带 `phase0/` + `skill-taxonomy/` 的目录），
换机器换目录不用改代码。环境不全会**明确报缺哪个文件**，不抛堆栈。

```bash
make env    # 打印当前配置来源与路径检查结果
```

### 依赖

**核心功能零第三方依赖**（纯标准库）。`Pillow` 仅 VLM provider 需要（把提示渲染成图）。

---

## 二、怎么跑

```bash
cd /workspace/output

# 单次训练
python3 medrep_coach.py --user 张伟 --disease D-NSCLC --dim DF --count 3

# 带药代回答（JSONL，每行 {qid, answer}）
python3 medrep_coach.py --user 张伟 --disease D-NSCLC --dim DF --count 3 \
  --answers coach-demo/answers_test.jsonl --out report.md

# 换交互形态（电话会触发「维度不可评 → 权重重分配」）
python3 medrep_coach.py --user 王芳 --disease D-NSCLC --dim DF --count 3 \
  --channel 电话 --answers coach-demo/answers_good.jsonl

# 一次跑完 5 个演示场景
bash coach-demo/demo.sh
```

参数：`--disease` 支持一期 8 个疾病（D-NSCLC / D-BREAST / D-HCC / D-GC / D-CRC / D-OVARIAN / D-GBM / D-CERVICAL）；`--dim` 支持 DF / TL / CE。

---

## 三、五个演示场景与验证结果

| # | 场景 | 输入 | 预期 | 实测 |
|---|---|---|---|---|
| 1 | 面访 · 违规回答 | 绝对化 + 宣称获批 + 保证疗效 | GATE-01 一票否决 | ✅ 综合分 0，等级「合规否决（不计入个人均分）」|
| 2 | 面访 · 合格回答 | 承认不确定 + 给核实路径 | 达标 | ✅ 4.97「达标」，GAP 无错误记录 |
| 3 | 电话形态 | 同 2，但形态为电话 | COM-04/05 不可评，权重重分配 | ✅ 话术 0.6→0.355、知识 0.4→0.645，报告显式标注未评维度 |
| 4 | 治疗格局维度 | 披露 vs 审批 | 正确区分两个状态 | ✅ 追问「具体要核对哪几项」|
| 5 | 证据解读维度 | 未作答 | 不得判「知识不足」 | ✅ 「暂不评定（本轮无可评分的知识维度）」|

**关键验证点**：GATE-01/02 触发时**仍判分**（已判违规 ≠ 不可评分），只有 GATE-03/04 才整题剔除。

---

## 四、实现的四个闸门

| 闸门 | 触发 | 处置 |
|---|---|---|
| **GATE-01** 合规硬红线 | 承诺疗效 / 宣称获批 / 回扣返利 / 保证效果 / 绝对化优越 | 本轮不通过，**不计入个人均分**，记入重练池 |
| **GATE-02** 适用边界越界 | 在研说成可用 / 研究阶段说能用 / 适应症断言 | MED-03 计 0 + **触发强制降档** |
| **GATE-03** 不可评分 | 药代明确表示不确定，且该题无已审核 rubric 支撑 | **整题剔除**：不判分、不进分母、不进 GAP，计入知识缺口率 |
| **GATE-04** 维度不可评 | 电话形态下无打断/非语言观测证据 | 该维度移出分母，**权重按剩余可评维度重新归一**，报告显式标注 |

---

## 五、九个评分维度

| 轨道 | 维度 |
|---|---|
| 沟通与应变（5）| COM-01 问题理解 / COM-02 回答结构 / COM-03 表达清晰 / COM-04 临场应变 / COM-05 情境适应 |
| 专业知识运用（4）| MED-01 知识准确性 / MED-02 证据运用 / MED-03 适用边界 / MED-04 专业与合规要求 |

评分 1–5 分制，逐维按各自锚点判定（不是笼统给一个基础分）。

**降档表**（1–5 分制）：

| 条件 | 上限 | 等级 |
|---|---|---|
| 触发 GATE-01 | 0 | 合规否决（不计入均分）|
| 触发 GATE-02 | 2.5 | 边界越界（强制降档）|
| 医学轨 < 2.5 | 2.5 | 知识不足（强制降档）|
| 医学轨 < 3.5 | 4.0 | 基本达标 |
| 其余 | 5.0 | 达标 |

**权重**：话术 60% / 知识 40%（可配置，随资历上调；上限 知识 60%）。

---

## 六、AI 医生的实现方式

**规则引擎，不调用 LLM。** 它做三件事：

1. **开场**：按角色风格调整措辞（直接 / 绕），但**医学内容不变**（AT05）
2. **追问**：读药代回答判断走向
   - 含核实路径 →「那您说的具体要核对哪几项？」（认可，转向具体动作）
   - 含绝对化/越界 →「您刚说的『XX』——您是依据哪份材料说的？」（触发风险，追依据）
   - 其他 → 常规深挖
3. **结束**：说明结束原因

**接 LLM 的位置很清楚**：把 `DoctorSim.opening` / `followup` 换成 LLM 调用即可，
**但必须保留「医学事实由知识版本锁定、不随角色情绪变化」的约束**——这是 AT05 的核心。

---

## 七、数据来源

### 新增：公开医药代表参考资料（候选知识）

`clinical/medrep-innovent-clinical-knowledge-v0.5/medrep_clinical_knowledge_v0.5.sqlite`
现含 `external_reference_documents` 与 `external_reference_points`：6 份可访问文献、
19 条带条款/页码的中文转述。资料包括 2026《医药代表管理办法》、WHO 药品推广伦理标准、
RDPAC 行业行为准则、中文教材章节、WHO/HAI 手册及一份明确标示“征求意见稿”的培养规范。

这批条目是人工整理的 **L1 / pending_human_review 候选层**，供评分标准设计与审核；
并未修改现有打分权重、自动评分逻辑或 `medical_usable` 医学事实集合。
教材中的产品、剂量、临床研究示例没有作为医学结论入库。
每条记录保留原文 URL、版本、适用范围、定位符与检索指纹。
`summary_sha256` 仅校验中文转述是否变化，不是原始 PDF 的文件哈希。

```bash
python3 knowledge_retrieval.py --references 禁忌症
python3 import_public_references.py  # 幂等重建/更新这批候选记录
```

`source_level` 是来源种类，不表示所有文献有相同的法律效力；实际适用范围见
`authority_scope`。尤其是 RDPAC 准则主要约束会员公司，WHO/HAI 手册从医生视角
观察推广活动，培养规范是征求意见稿。规则进入正式评分前仍须逐条人工审核。

| 环节 | 来源 |
|---|---|
| 考点候选 | 一期课程（DF/TL/CE）的检验题 + 48 条场景种子（课件语料出处可溯源）|
| 评分锚点与闸门 | `phase0/D8a-评分表草案.json` |
| 能力点 | `skill-taxonomy/skill-taxonomy.json`（222 个）|
| 场景种子 | `scenarios/scenario-library.jsonl`（48 条，带语料出处）|

---

## 七之二、LLM 驱动的 AI 医生

**LLM 负责「像人说话」，数据库负责「说什么」。医学事实一个字都不来自模型记忆。**

三层不可跳过：检索（带出处的事实）→ 受控提示 → 生成 → **FactGuard 独立校验**。

### 三种 Provider

| Provider | 说明 | 何时用 |
|---|---|---|
| `minimax_text` | MiniMax 文本 API，温度 0.3 | **生产**（需 `MINIMAX_API_KEY`）|
| `vision_text` | 渲染成图 → VLM 读图 | **当前环境即可用**，无需 key |
| `mock` | 从事实包合成合规回答 | 测试与回归（确定性、无网络）|

三者共用**完全相同**的提示与校验层，所以换 provider 不影响医学安全性。

```bash
# 规则引擎（默认，零依赖）
python3 medrep_coach.py --user 张伟 --disease D-NSCLC --dim DF --count 3 \
  --answers coach-demo/answers_good.jsonl

# LLM 医生
python3 medrep_coach.py --user 张伟 --disease D-NSCLC --dim TL --count 1 --llm

# 显式指定 provider（不可用直接报错，不静默换人）
python3 medrep_coach.py ... --llm --llm-provider minimax_text
```

### 实测：医生真活了

```
**医生**：不能先定下来，建议必须等驱动基因结果出全、明确适用人群后再做决定。
同时需要向您说明，达伯舒在非小细胞肺癌上并非获批适应症，不得表述为可用于
该疾病，具体信息需要按最新 NMPA 说明书/企业合规版本核实。

**药代**：达伯舒是 PD-1 方向的产品，适用范围要按最新 NMPA 说明书和企业合规
版本核实，我不替您判断适用人群。等驱动基因和 PD-L1 检测结果都出来，我们医学
团队可以一起过一遍证据口径。

**医生**：[Q1] 考虑到驱动基因结果对后续治疗方案的决策具有决定性影响，在等待
报告期间，您是否已将特定的基因突变情况作为判定免疫单药或联合治疗方案的先决
硬指标？如需进一步明确不同方案的获批人群边界，我可以为您提供最新的 NMPA 说
明书供参考。
```

**「达伯舒在 NSCLC 并非获批适应症」这句来自数据库事实，不是模型记忆。**

### AT05 实测通过

同一医学问题用 4 种医生风格各跑一次，**核心医学事实无矛盾**：

| 核心事实 | 直接 | 绕 | 分析 | 表现 |
|---|---|---|---|---|
| 靶点 PD-1 | ✓ | ✓ | ✓ | ✓ |
| 声明非适应症 | ✓ | ✓ | ✓ | ✓ |
| 要求核实 | ✓ | ✓ | ✓ | ✓ |
| 宣称获批（绝不应有） | ✗ | ✗ | ✗ | ✗ |

判定原则是**矛盾检测**而非「每项都必须出现」——省略可选信息不算矛盾，
只有「一个说可以用于、另一个说不是适应症」这种直接冲突才算破坏。

详见 `LLM医生说明.md`。

---

## 八、还没做的（诚实清单）

| 项 | 状态 | 说明 |
|---|---|---|
| LLM 驱动的 AI 医生 | ✅ | **已接入**（检索→提示→生成→校验四层）；当前用 VLM，生产切文本 API |
| 合规规则的法条依据 | ⬜ | 规则来自语料归纳，**法条依据需合规人工提供**（禁止 web 检索补文号）|
| 纯语义规避识别 | ⬜ | 不含标记词的规避（如「让科室好写点意见」）仍会漏判——D07-1b，需标注集验证 |
| LLM 路径的标注集校准 | ⬜ | 与规则层同样的问题：阈值未经真实数据校准 |
| 语音链路 | ⬜ | ASR→文本编排→TTS 未实现 |
| 复盘链路 | ⬜ | V1.3 §2.1–2.3（DebriefRaw→Observation→CoverageMap）未接 |
| 专家画像 | ⬜ | V1.3 §1.2 的 ExpertRef 未做；当前画像卡是纯合成角色 |
| 日报 | ⬜ | V1.3 板块 03 未做 |
| 自动评分校准 | ⬜ | 现在的锚点判定是规则近似，未经培训师标注集校准 |
| 医学审核 | ⬜ | 全部内容 `pending_medical_review`，报告不作最终评价依据 |

**最要紧的两件**：① 评分锚点要经培训师标注集校准（现在是我的规则近似）；
② 课程要签审进已审核层（V1.3 §0.2 硬约束）。

---

## 九、文件

```
coach-demo/
├── medrep_coach.py          主程序
├── knowledge_retrieval.py   检索层（临床库 → 带出处的事实包）
├── llm_provider.py          Provider + 提示构造 + FactGuard
├── llm_doctor.py            LLM 驱动的医生
├── compliance_rules.py      共享合规规则（引擎与 FactGuard 共用一份）
├── decisions.py             已拍板决策（D08a-1~3）
└── LLM医生说明.md            LLM 路径完整文档
├── demo.sh                  7 场景演示
├── answers_test.jsonl       违规回答样本
├── answers_good.jsonl       合格回答样本
├── answers_tl.jsonl         治疗格局维度
└── answers_ce.jsonl         证据解读维度
```

### 四条自检命令

```bash
python3 phase0/verify_phase0_consistency.py   # 29 项交叉验收
python3 check_rule_quality.py                 # 规则质量（防空匹配/尾随竖线）
python3 verify_llm_path.py                    # LLM 四层自检（离线，Mock）
python3 verify_at05.py                        # AT05 检测器自测
python3 phase0/run_baseline_regression.py     # 101 条判定回归
bash coach-demo/demo.sh                        # 8 场景端到端（含 LLM 场景）
```
