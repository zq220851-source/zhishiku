/* Generated from the same TypeScript sources used by the Next application. */
(function(){
 const modules={
  './errors': function(require, module, exports) {
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Module2Error = void 0;
exports.invalid = invalid;
exports.object = object;
exports.text = text;
exports.list = list;
exports.strings = strings;
exports.unique = unique;
class Module2Error extends Error {
    code;
    status;
    constructor(code, message, status = 400) {
        super(message);
        this.code = code;
        this.status = status;
    }
}
exports.Module2Error = Module2Error;
function invalid(message) { throw new Module2Error('INVALID_INPUT', message); }
function object(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value))
        invalid('需要 JSON 对象。');
    return value;
}
function text(value, max = 200) {
    if (typeof value !== 'string' || !value.trim() || value.length > max)
        invalid('字段不能为空或超过长度限制。');
    return value;
}
function list(value, max = 100) {
    if (!Array.isArray(value) || value.length > max)
        invalid('列表不合法或超过长度限制。');
    return value;
}
function strings(value, max = 100) {
    const result = list(value, max).map(v => text(v));
    if (new Set(result).size !== result.length)
        invalid('标识或枚举值不能重复。');
    return result;
}
function unique(values) {
    if (new Set(values.map(v => v.id)).size !== values.length)
        invalid('对象标识不能重复。');
}

  },
  './fixture': function(require, module, exports) {
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.sampleReflection = void 0;
exports.validateTaskInput = validateTaskInput;
exports.mainFixture = mainFixture;
const errors_1 = require("./errors");
function validateTaskInput(value) {
    const input = (0, errors_1.object)(value), cb = (0, errors_1.object)(input.codebook);
    const capabilities = (0, errors_1.list)(cb.capabilities).map(v => { const a = (0, errors_1.object)(v); return { id: (0, errors_1.text)(a.id), description: (0, errors_1.text)(a.description, 1000) }; });
    (0, errors_1.unique)(capabilities);
    const skills = (0, errors_1.list)(cb.skills).map(v => {
        const a = (0, errors_1.object)(v), capabilityIds = (0, errors_1.strings)(a.capabilityIds);
        if (!capabilityIds.length || capabilityIds.some(id => !capabilities.some(c => c.id === id)))
            (0, errors_1.invalid)('考点引用了不存在的能力单元。');
        return { id: (0, errors_1.text)(a.id), topic: (0, errors_1.text)(a.topic), cognitiveTask: (0, errors_1.text)(a.cognitiveTask), evidenceBoundary: (0, errors_1.text)(a.evidenceBoundary, 1000), capabilityIds };
    });
    (0, errors_1.unique)(skills);
    const evidence = (0, errors_1.list)(input.evidence, 30).map(v => {
        const e = (0, errors_1.object)(v);
        if (e.usage !== 'TEST_ONLY')
            (0, errors_1.invalid)('输入替身不能自行声明正式医学批准。');
        return { id: (0, errors_1.text)(e.id), version: (0, errors_1.text)(e.version), title: (0, errors_1.text)(e.title), content: (0, errors_1.text)(e.content, 20000), usage: 'TEST_ONLY' };
    });
    (0, errors_1.unique)(evidence);
    const plan = (0, errors_1.list)(input.plan).map(v => {
        const a = (0, errors_1.object)(v), skillId = (0, errors_1.text)(a.skillId), evidenceIds = (0, errors_1.strings)(a.evidenceIds);
        if (!skills.some(s => s.id === skillId) || evidenceIds.some(id => !evidence.some(e => e.id === id)))
            (0, errors_1.invalid)('准备计划引用不存在的考点或资料。');
        if ('practiced' in a || 'evaluated' in a || 'score' in a)
            (0, errors_1.invalid)('演练和评分必须来自实际记录，不能通过输入标记伪造。');
        return { skillId, question: (0, errors_1.text)(a.question, 2000), rationale: (0, errors_1.text)(a.rationale, 2000), evidenceIds };
    });
    if (!capabilities.length || !skills.length || !plan.length || new Set(plan.map(p => p.skillId)).size !== plan.length)
        (0, errors_1.invalid)('代码本和准备计划不能为空或重复。');
    return { fixtureId: (0, errors_1.text)(input.fixtureId), title: (0, errors_1.text)(input.title), knowledgeVersion: (0, errors_1.text)(input.knowledgeVersion),
        scenarioVersion: (0, errors_1.text)(input.scenarioVersion), strategyVersion: (0, errors_1.text)(input.strategyVersion),
        codebook: { version: (0, errors_1.text)(cb.version), capabilities, skills }, evidence, plan };
}
/** Fictional input data only. No analysis, review decision or predicted output is seeded. */
function mainFixture() {
    return {
        fixtureId: 'research-a-main-v1', title: '虚构研究 A · 学术交流准备', knowledgeVersion: 'test-evidence-v1', scenarioVersion: 'SC1', strategyVersion: 'ST1',
        codebook: { version: 'test-codebook-v1', capabilities: [
                { id: 'endpoint', description: '解释主要终点的定义' }, { id: 'population', description: '解释入组条件与人群范围' },
                { id: 'subgroup', description: '解释亚组结果及其探索性性质' }, { id: 'extrapolation', description: '说明亚组结果的外推限制' },
            ], skills: [
                { id: 'endpoint-explanation', topic: '虚构研究 A', cognitiveTask: '解释', evidenceBoundary: '主要终点定义', capabilityIds: ['endpoint'] },
                { id: 'population-explanation', topic: '虚构研究 A', cognitiveTask: '解释', evidenceBoundary: '入组与排除条件', capabilityIds: ['population'] },
                { id: 'subgroup-explanation', topic: '虚构研究 A', cognitiveTask: '解释', evidenceBoundary: '亚组结果及探索性性质', capabilityIds: ['subgroup'] },
                { id: 'subgroup-extrapolation', topic: '虚构研究 A', cognitiveTask: '解释并评价', evidenceBoundary: '亚组结果及外推限制', capabilityIds: ['subgroup', 'extrapolation'] },
            ] },
        evidence: [{ id: 'E1', version: '1', title: '虚构研究 A 测试资料（非医学事实）', usage: 'TEST_ONLY',
                content: '本材料完全虚构，仅验证软件流程。主要终点为预先定义的测试终点。研究有指定入组和排除条件。亚组结果为探索性结果，不支持直接推广到其他人群。不包含真实药物、疗效数值或治疗建议。' }],
        plan: [
            { skillId: 'endpoint-explanation', question: '如何解释主要终点？', rationale: '本次准备覆盖研究基本终点。', evidenceIds: ['E1'] },
            { skillId: 'population-explanation', question: '研究的入组人群是什么？', rationale: '本次准备覆盖研究入组范围。', evidenceIds: ['E1'] },
        ],
    };
}
exports.sampleReflection = '这次讨论的是虚构研究 A。对方先问主要终点是什么意思，我觉得这部分解释清楚了。后来又问亚组结果能不能推广到其他人群，我不太确定，没能讲清楚。我觉得可能是之前没有准备到这部分。对方最后是否认可，我不知道。';

  },
  './demo-data': function(require, module, exports) {
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.demoTasks = void 0;
exports.researchB = researchB;
exports.demoCatalog = demoCatalog;
exports.demoCases = demoCases;
const fixture_1 = require("./fixture");
function researchB() {
    return {
        fixtureId: 'fictional-research-b-v1', title: '虚构研究 B · 三个月观察窗口', knowledgeVersion: 'b-knowledge-v1', scenarioVersion: 'b-catalog-v1', strategyVersion: 'b-strategy-v1',
        codebook: { version: 'b-codebook-v1', capabilities: [
                { id: 'observation-window', description: '准确描述三个月观察窗口' },
                { id: 'long-term-limitation', description: '说明资料不包含一年后结果' },
                { id: 'uncertainty-expression', description: '解释未知信息时不作长期效果保证' },
            ], skills: [
                { id: 'window-explanation', topic: '虚构研究 B', cognitiveTask: '解释', evidenceBoundary: '观察窗口', capabilityIds: ['observation-window'] },
                { id: 'longterm-boundary-judgment', topic: '虚构研究 B', cognitiveTask: '评价证据边界', evidenceBoundary: '长期效果未知', capabilityIds: ['long-term-limitation', 'uncertainty-expression'] },
            ] },
        evidence: [{ id: 'B-E1', version: '1', title: '虚构研究 B 测试资料（非医学事实）', usage: 'TEST_ONLY', content: '此资料纯属虚构，观察窗口仅为三个月，不包含一年后的结果，不支持保证长期效果。没有真实药物、疾病或疗效数据。' }],
        plan: [{ skillId: 'window-explanation', question: '研究观察了多长时间？', rationale: '练习解释观察窗口。', evidenceIds: ['B-E1'] }],
    };
}
function demoCatalog(input) {
    if (input.fixtureId === 'research-a-main-v1' && input.knowledgeVersion === 'test-evidence-v1' && input.codebook.version === 'test-codebook-v1' && input.scenarioVersion.startsWith('SC1'))
        return [
            { contentId: 'A-content-endpoint', version: '1', skillId: 'endpoint-explanation', coveredCapabilityIds: ['endpoint'], evidenceIds: ['E1'], status: 'ELIGIBLE_TEST_ONLY' },
            { contentId: 'A-content-population', version: '1', skillId: 'population-explanation', coveredCapabilityIds: ['population'], evidenceIds: ['E1'], status: 'ELIGIBLE_TEST_ONLY' },
        ];
    if (input.fixtureId === 'fictional-research-b-v1' && input.knowledgeVersion === 'b-knowledge-v1' && input.codebook.version === 'b-codebook-v1' && input.scenarioVersion.startsWith('b-catalog-v1'))
        return [
            { contentId: 'B-content-window', version: '1', skillId: 'window-explanation', coveredCapabilityIds: ['observation-window'], evidenceIds: ['B-E1'], status: 'ELIGIBLE_TEST_ONLY' },
            { contentId: 'B-content-longterm', version: '1', skillId: 'longterm-boundary-judgment', coveredCapabilityIds: ['long-term-limitation', 'uncertainty-expression'], evidenceIds: ['B-E1'], status: 'ELIGIBLE_TEST_ONLY' },
        ];
    return undefined;
}
function demoCases(input) {
    if (input.fixtureId === 'research-a-main-v1' && input.knowledgeVersion === 'test-evidence-v1' && input.codebook.version === 'test-codebook-v1' && input.scenarioVersion.startsWith('SC1'))
        return [
            { id: 'A-dev-routine', partition: 'DEVELOPMENT', focus: 'BASIC', expectedSkillIds: ['endpoint-explanation', 'population-explanation'], budget: 2 },
            { id: 'A-dev-boundary', partition: 'DEVELOPMENT', focus: 'EXTRAPOLATION', expectedSkillIds: ['endpoint-explanation', 'subgroup-extrapolation'], budget: 2 },
            { id: 'A-holdout-routine', partition: 'HOLDOUT', focus: 'BASIC', expectedSkillIds: ['endpoint-explanation', 'population-explanation'], budget: 2 },
            { id: 'A-holdout-boundary', partition: 'HOLDOUT', focus: 'EXTRAPOLATION', expectedSkillIds: ['endpoint-explanation', 'subgroup-extrapolation'], budget: 2 },
        ];
    if (input.fixtureId === 'fictional-research-b-v1' && input.knowledgeVersion === 'b-knowledge-v1' && input.codebook.version === 'b-codebook-v1' && input.scenarioVersion.startsWith('b-catalog-v1'))
        return [
            { id: 'B-dev-window', partition: 'DEVELOPMENT', focus: 'BASIC', expectedSkillIds: ['window-explanation'], budget: 1 },
            { id: 'B-dev-longterm', partition: 'DEVELOPMENT', focus: 'EXTRAPOLATION', expectedSkillIds: ['longterm-boundary-judgment'], budget: 1 },
            { id: 'B-holdout-window', partition: 'HOLDOUT', focus: 'BASIC', expectedSkillIds: ['window-explanation'], budget: 1 },
            { id: 'B-holdout-longterm', partition: 'HOLDOUT', focus: 'EXTRAPOLATION', expectedSkillIds: ['longterm-boundary-judgment'], budget: 1 },
        ];
    return undefined;
}
exports.demoTasks = { A: fixture_1.mainFixture, B: researchB };

  },
  './decision-engine': function(require, module, exports) {
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.decideSharedChange = decideSharedChange;
exports.validateCatalog = validateCatalog;
exports.validateStrategyCases = validateStrategyCases;
function decideSharedChange(input, difference, catalog, releasedContentSkills = []) {
    const skill = input.codebook.skills.find(s => s.id === difference.skillId);
    const base = { skillId: skill?.id ?? null, missingCapabilities: difference.missingCapabilityIds, catalogContentIds: [] };
    if (!skill || difference.usability !== 'USABLE' || difference.coverage === 'UNKNOWN')
        return { ...base, kind: 'INSUFFICIENT_DATA', reason: '问题或考点映射仍不明确，暂不改变共享内容和策略。' };
    if (!difference.gapCandidate)
        return { ...base, kind: 'PERSONAL_ONLY', reason: '没有可证实的准备覆盖缺口，不因此修改共享内容或选题。' };
    if (!catalog)
        return { ...base, kind: 'INSUFFICIENT_DATA', reason: '缺少可核验的训练内容目录，无法判断缺内容还是没有选到。' };
    const matching = catalog.filter(c => c.skillId === skill.id && c.status === 'ELIGIBLE_TEST_ONLY');
    const covered = new Set(matching.flatMap(c => c.coveredCapabilityIds));
    const fullContent = releasedContentSkills.includes(skill.id) || skill.capabilityIds.every(id => covered.has(id));
    const resultBase = { ...base, catalogContentIds: matching.map(c => c.contentId) };
    if (!fullContent)
        return { ...resultBase, kind: 'CONTENT', reason: `现有训练内容未覆盖「${skill.evidenceBoundary}」的全部能力单元，需要补充或修订共享场景。` };
    if (!input.plan.some(p => p.skillId === skill.id))
        return { ...resultBase, kind: 'STRATEGY', reason: `「${skill.evidenceBoundary}」已有可用训练内容，但本次冻结计划没有选中；应在同等题量下比较选题方案。` };
    return { ...resultBase, kind: 'PERSONAL_ONLY', reason: '内容和选题都已覆盖该能力，先优先验证个人表现，不机械修改团队资产。' };
}
function validateCatalog(input, entries) {
    const seen = new Set();
    if (!Array.isArray(entries) || entries.length > 100)
        throw new Error('训练内容目录无效。');
    for (const item of entries) {
        const skill = input.codebook.skills.find(s => s.id === item.skillId);
        if (!item.contentId || !item.version || seen.has(item.contentId) || !skill || item.status !== 'ELIGIBLE_TEST_ONLY' ||
            !Array.isArray(item.coveredCapabilityIds) || !item.coveredCapabilityIds.length ||
            item.coveredCapabilityIds.some(id => !skill.capabilityIds.includes(id)) ||
            !Array.isArray(item.evidenceIds) || item.evidenceIds.some(id => !input.evidence.some(e => e.id === id)))
            throw new Error('训练内容目录引用了不存在的能力或资料。');
        seen.add(item.contentId);
    }
}
function validateStrategyCases(input, cases) {
    if (!Array.isArray(cases) || cases.length > 30 || cases.some(c => !c.id ||
        !['DEVELOPMENT', 'HOLDOUT'].includes(c.partition) || !['BASIC', 'EXTRAPOLATION', 'UNKNOWN'].includes(c.focus) ||
        !Number.isInteger(c.budget) || c.budget < 1 || c.budget > 10 || !Array.isArray(c.expectedSkillIds) ||
        c.expectedSkillIds.some(s => !input.codebook.skills.some(x => x.id === s))))
        throw new Error('选题对照样例无效。');
}

  },
  './strategy': function(require, module, exports) {
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.selectSkills = selectSkills;
exports.compareStrategyCases = compareStrategyCases;
exports.compareStrategies = compareStrategies;
const demo_data_1 = require("./demo-data");
const fixture_1 = require("./fixture");
/** Capacity is fixed between baseline and proposed selection; no outcome labels are passed to the selector. */
function selectSkills(available, input, strategy) {
    const capacity = Math.max(0, Math.min(10, Math.floor(input.budget)));
    const base = [...new Set([...(input.baselineSkillIds ?? available), ...available])].filter(s => available.includes(s));
    if (strategy === 'BASELINE' || input.focus !== 'EXTRAPOLATION' || !input.prioritySkillId || !available.includes(input.prioritySkillId))
        return base.slice(0, capacity);
    // Keep the first baseline anchor only when capacity >1; re-rank the remaining slot without increasing work.
    const anchor = capacity > 1 ? base.slice(0, 1) : [];
    const order = [...new Set([...anchor, input.prioritySkillId, ...base])];
    return order.slice(0, capacity);
}
/** Authored independent test cases: evaluate two selectors against the same content and budget. */
function compareStrategyCases(available, cases, baseline, prioritySkillId) {
    return cases.map(c => {
        const args = { focus: c.focus, budget: c.budget, prioritySkillId, baselineSkillIds: baseline };
        const old = selectSkills(available, args, 'BASELINE'), next = selectSkills(available, args, 'FOCUS');
        return { partition: c.partition, caseId: c.id, old, next,
            added: next.filter(id => c.expectedSkillIds.includes(id) && !old.includes(id)),
            lost: old.filter(id => c.expectedSkillIds.includes(id) && !next.includes(id)),
            valid: old.length === next.length && old.length <= c.budget && c.expectedSkillIds.every(id => available.includes(id)) };
    });
}
/** Legacy A demo preview; production/generic decisions call compareStrategyCases with their own fixtures. */
function compareStrategies(available) {
    const input = (0, fixture_1.mainFixture)();
    return compareStrategyCases(available, (0, demo_data_1.demoCases)(input), input.plan.map(p => p.skillId), 'subgroup-extrapolation');
}

  },
  './lab-cases': function(require, module, exports) {
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.labCases = labCases;
exports.labInput = labInput;
exports.labCatalog = labCatalog;
exports.labDifference = labDifference;
exports.evaluateLab = evaluateLab;
/** Transparent synthetic structured-analysis cases, NOT a claim of real model accuracy. */
const fixture_1 = require("./fixture");
const demo_data_1 = require("./demo-data");
const decision_engine_1 = require("./decision-engine");
const strategy_1 = require("./strategy");
const CASES = [
    { id: 'A1', study: 'A', title: '缺少共享训练内容', utterance: '医生后来问，这个亚组能不能推到别的人群。我那会儿没准备到这块，解释不清。', skillId: 'subgroup-extrapolation', coverage: 'NONE', gap: true, catalog: 'DEFAULT', released: [], expected: 'CONTENT', why: '准备未覆盖，场景目录中也没有完整亚组外推练习' },
    { id: 'A2', study: 'A', title: '补内容后仍没选到', utterance: '我这回准备终点和人群，医生却追问亚组外推，还是没练到。', skillId: 'subgroup-extrapolation', coverage: 'NONE', gap: true, catalog: 'DEFAULT', released: ['subgroup-extrapolation'], expected: 'STRATEGY', why: '模拟存在已审核的共享内容，但冻结计划仍未选择' },
    { id: 'A3', study: 'A', title: '只是个人解释不清', utterance: '这题我练过了，可真问起来，我把外推限制说得太绝对。', skillId: 'endpoint-explanation', coverage: 'FULL', gap: false, catalog: 'DEFAULT', released: [], expected: 'PERSONAL_ONLY', why: '该题已有准备覆盖，不以自述困难推定团队内容缺项' },
    { id: 'A4', study: 'A', title: '问题归属还不明确', utterance: '反正有个问题，我不记得具体问的是什么了。', skillId: 'subgroup-extrapolation', coverage: 'UNKNOWN', usable: false, gap: false, catalog: 'DEFAULT', released: [], expected: 'INSUFFICIENT_DATA', why: '问题不可用，不能强行归因' },
    { id: 'B1', study: 'B', title: '内容存在、选题未命中', utterance: '医生问一年之后呢？这个我们有训练材料，但这次没选，我当时卡住了。', skillId: 'longterm-boundary-judgment', coverage: 'NONE', gap: true, catalog: 'DEFAULT', released: [], expected: 'STRATEGY', why: '研究 B 有边界训练目录，但原计划只选观察窗口' },
    { id: 'B2', study: 'B', title: '目录缺失，不装作知道', utterance: '一年后是不是一样？我记得没准备这题。', skillId: 'longterm-boundary-judgment', coverage: 'NONE', gap: true, catalog: 'MISSING', released: [], expected: 'INSUFFICIENT_DATA', why: '缺少真实可验证的目录，不能把准备计划当目录' },
    { id: 'B3', study: 'B', title: '只覆盖了部分能力', utterance: '我知道只有三个月，但不知道怎么解释不能保证一年后的结果。', skillId: 'longterm-boundary-judgment', coverage: 'PARTIAL', gap: true, catalog: 'PARTIAL', released: [], expected: 'CONTENT', why: '目录仅有长期限制，没有不作保证的表达能力训练' },
    { id: 'B4', study: 'B', title: '已覆盖且本人自述顺利', utterance: '医生问观察多久，我说三个月，对方没有再问。', skillId: 'window-explanation', coverage: 'FULL', gap: false, catalog: 'DEFAULT', released: [], expected: 'PERSONAL_ONLY', why: '不能因有复盘就强行产生进化' },
    { id: 'B5', study: 'B', title: '考点映射仍未知', utterance: '医生突然问了个我不确定的问题，具体忘了。', skillId: 'non-existent', coverage: 'UNKNOWN', gap: true, catalog: 'DEFAULT', released: [], expected: 'INSUFFICIENT_DATA', why: '未映射到真实冻结考点' },
];
function labCases() { return CASES; }
function labInput(c) { return c.study === 'A' ? (0, fixture_1.mainFixture)() : (0, demo_data_1.researchB)(); }
function labCatalog(c) {
    if (c.catalog === 'MISSING')
        return undefined;
    const catalog = (0, demo_data_1.demoCatalog)(labInput(c));
    return c.catalog === 'PARTIAL' ? catalog.map(x => x.skillId === 'longterm-boundary-judgment' ?
        { ...x, coveredCapabilityIds: ['long-term-limitation'] } : x) : catalog;
}
function labDifference(c) {
    return { questionUnitId: 'model-extracted-question', skillId: c.skillId, usability: c.usable === false ? 'AMBIGUOUS' : 'USABLE',
        coverage: c.coverage, comparedSkillIds: [], missingCapabilityIds: [], reason: '测试用的结构化分析输出',
        performance: [], personalSignal: 'PENDING_VERIFY', gapCandidate: c.gap };
}
function evaluateLab(c) {
    const input = labInput(c);
    const result = (0, decision_engine_1.decideSharedChange)(input, labDifference(c), labCatalog(c), c.released);
    const catalog = labCatalog(c);
    const available = [...new Set([...input.plan.map(p => p.skillId), ...(catalog ?? []).map(x => x.skillId), ...c.released])];
    const cases = (0, demo_data_1.demoCases)(input);
    const comparisons = (0, strategy_1.compareStrategyCases)(available, cases, input.plan.map(p => p.skillId), c.skillId);
    const preview = comparisons.find(r => r.partition === 'HOLDOUT' && r.added.length > 0);
    return { input, result, passed: result.kind === c.expected, preview, comparisons };
}

  }
 };
 const loaded={};
 function require(id){ if(!Object.prototype.hasOwnProperty.call(modules,id)) throw new Error("Unknown module: "+id); if(loaded[id])return loaded[id].exports;const module={exports:{}};loaded[id]=module;modules[id](require,module,module.exports);return module.exports; }
 window.medrepLab=require("./lab-cases");
})();
