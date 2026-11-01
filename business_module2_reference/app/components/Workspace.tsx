'use client';
import { useEffect, useRef, useState } from 'react';
import { SpeechInput } from './SpeechInput';
import { EvolutionPanel } from './EvolutionPanel';
import { CoreLab } from './CoreLab';
import type { DiscoveryRun } from '../../lib/discovery';
import type { EvolutionView } from '../../lib/evolution-types';
import { LearningPanel } from './LearningPanel';
import type { LearningDashboard } from '../../lib/learning-types';
import { RiskInboxPanel } from './RiskInboxPanel';
import { ROLES, roleNames } from '../../lib/roles';
import type { Actor, RiskSummary, Role, Feedback, Task, TaskInput, StatementType } from '../../lib/types';
type State = { discovery: DiscoveryRun[]; evolution: EvolutionView; learning: LearningDashboard; actor: Actor; risks: RiskSummary[]; tasks: Task[]; task?: Task; feedback?: Feedback[]; fixture: TaskInput; fixtures?: { A: TaskInput; B: TaskInput }; sampleReflection: string; model: { configured: boolean; authorized: boolean; name: string | null } };
const coverageNames = { FULL: '完整覆盖', PARTIAL: '部分覆盖', NONE: '未覆盖', UNKNOWN: '覆盖未知' };
const states = { SAVED: '原文已保存', PROCESSING: '正在分析', FAILED: '分析未完成', ANALYZED: '分析完成 · 待复核', RESTRICTED: '已隔离', CANCELED: '任务已取消' };
const types: Record<StatementType, string> = { REPORTED_QUESTION: '回忆的问题', SELF_REPORTED_RESPONSE: '自述回应', INTERPRETATION: '个人推测', MEDICAL_CLAIM: '待核验医学主张', CONTEXT: '情境', UNKNOWN: '未知' };
async function api<T>(body?: unknown, taskId?: string, key?: string): Promise<T> {
  const response = await fetch('/api/module2' + (taskId ? `?taskId=${encodeURIComponent(taskId)}` : ''), { method: body === undefined ? 'GET' : 'POST', cache: 'no-store', headers: { 'Content-Type': 'application/json', ...(key ? { 'Idempotency-Key': key } : {}) }, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
  const result = await response.json(); if (!response.ok) throw new Error(result.error?.message || '请求失败。'); return result.data as T;
}
export function Workspace() {
  const [screen, setScreen] = useState<'REFLECTION' | 'LEARNING' | 'EVOLUTION' | 'LAB'>('REFLECTION');
  const [focus, setFocus] = useState('BASIC');
  const [data, setData] = useState<State>(); const [selected, setSelected] = useState<string>();
  const [error, setError] = useState(''); const [notice, setNotice] = useState(''); const [busy, setBusy] = useState(false);
  const [supplement, setSupplement] = useState<Record<string,string>>({});
  const [rawSource, setRawSource] = useState<'TEXT' | 'VOICE_TRANSCRIPT'>('TEXT');
  const [raw, setRaw] = useState(''); const [confirmed, setConfirmed] = useState(false); const [occurred, setOccurred] = useState(false);
  const [editing, setEditing] = useState<Feedback>(); const [fixtureText, setFixtureText] = useState(''); const [catalogText, setCatalogText] = useState('');
  const operation = useRef<{ fingerprint: string; key: string } | undefined>(undefined);
  async function load(taskId = selected) { setData(await api<State>(undefined, taskId)); }
  useEffect(() => { let active = true; api({ action: 'session' }).then(() => api<State>()).then(v => { if (active) setData(v); }).catch(e => { if (active) setError(e.message); }); return () => { active = false; }; }, []);
  async function run(fn: () => Promise<void>) { setBusy(true); setError(''); setNotice(''); try { await fn(); } catch (e) { setError(e instanceof Error ? e.message : '操作失败。'); } finally { setBusy(false); } }
  async function mutate<T>(value: unknown): Promise<T> {
    const fingerprint = JSON.stringify(value);
    if (operation.current?.fingerprint !== fingerprint) operation.current = { fingerprint, key: crypto.randomUUID() };
    const result = await api<T>(value, undefined, operation.current.key); operation.current = undefined; return result;
  }
  const task = data?.task;
  function reset() { setRawSource('TEXT'); setRaw(''); setEditing(undefined); setConfirmed(false); setOccurred(false); }
  async function select(id: string) { await run(async () => { setData(await api<State>(undefined, id)); setSelected(id); reset(); }); }
  const canceled = task?.status === 'CANCELED';
  return <main>
    <header><a href="/" className="brand">MedRep <strong>Coach</strong></a><span>模块 02 · 反馈进化</span><span className="badge">独立测试环境</span></header>
    <section className="intro"><p className="eyebrow">从这一次，准备下一次</p><h1>让每次交流，成为下一次的依据。</h1><p>保留你的原话，看清准备与现场的差异，再推动后续训练。</p></section>
    <nav className="steps"><span>01 关联准备计划</span><span>02 确认复盘原文</span><span>03 提取与差异分析</span><span>04 个人训练与后续验证</span></nav>
    {error && <div role="alert" className="alert error">{error}</div>}{notice && <div role="status" className="alert">{notice}</div>}
    {!data ? <section className="card"><p>正在建立测试会话…</p>{error && <button onClick={() => window.location.reload()}>重新进入</button>}</section> : <>
      <section className="model-status"><span className={`dot ${data.model.configured && data.model.authorized ? 'ready' : ''}`} /><span>{data.model.configured ? data.model.authorized ? `模型已配置：${data.model.name}` : '模型已配置，尚未允许发送测试资料' : '模型 API 待配置'}</span><small>未配置时保留原文，不生成模拟分析结果。</small></section>
      <section className="role-switch"><label>测试职责 <select aria-label="测试职责" disabled={busy} value={data.actor.role} onChange={event => run(async () => {
        await api({ action: 'switchRole', role: event.target.value as Role }); await load(); setNotice('测试职责已切换，原文草稿仍保留。');
      })}>{ROLES.map(role => <option key={role} value={role}>{roleNames[role]}</option>)}</select></label><small>同一测试者可切换职责，服务端分别校验权限；不是企业账号授权。</small></section>
      <nav className="actions" aria-label="工作区"><button className={screen === 'REFLECTION' ? 'primary' : 'secondary'} onClick={() => setScreen('REFLECTION')}>1. 拜访后复盘</button><button className={screen === 'LEARNING' ? 'primary' : 'secondary'} onClick={() => setScreen('LEARNING')}>2. 我的后续练习</button><button className={screen === 'EVOLUTION' ? 'primary' : 'secondary'} onClick={() => setScreen('EVOLUTION')}>3. 团队训练改进</button><button className={screen === 'LAB' ? 'primary' : 'secondary'} onClick={() => setScreen('LAB')}>4. 测试实验台</button></nav>
      {screen === 'LAB' && <CoreLab />}
      {screen === 'LEARNING' && <LearningPanel key={data.actor.role} actor={data.actor} data={data.learning} busy={busy} action={async value => {
        setBusy(true); setError(''); try { const result = await mutate(value); await load(); return result; }
        catch (e) { setError(e instanceof Error ? e.message : '操作未完成'); throw e; } finally { setBusy(false); }
      }} />}
      {screen === 'EVOLUTION' && <EvolutionPanel discovery={data.discovery} actor={data.actor} data={data.evolution} busy={busy} action={async value => {
        setBusy(true); setError(''); try { const result = await mutate(value); await load(); return result; }
        catch (e) { setError(e instanceof Error ? e.message : '操作未完成'); throw e; } finally { setBusy(false); }
      }} />}
      <RiskInboxPanel key={data.actor.role} actor={data.actor} risks={data.risks} busy={busy} onError={setError} onChange={async (risk, state, note) => {
        setBusy(true); setError('');
        try { await mutate({ action: 'updateRisk', riskId: risk.id, state, note, expectedRevision: risk.revision }); await load(); setNotice('风险处理状态已更新并留痕。'); }
        catch (error) { setError(error instanceof Error ? error.message : '处理未完成。'); await load(); throw error; }
        finally { setBusy(false); }
      }} />
      {screen === 'REFLECTION' && (data.actor.role === 'EMPLOYEE' ? <div className="workspace"><aside>
        <section className="card"><div className="heading"><h2>准备任务</h2><span>{data.tasks.length}</span></div><button className="primary wide" disabled={busy} onClick={() => run(async () => { const created = await mutate<Task>({ action: 'createTask', fixture: data.fixtures?.A ?? data.fixture }); await load(created.id); setSelected(created.id); reset(); setNotice('测试任务已创建，准备计划与资料版本已冻结。'); })}>＋ 创建研究 A 测试任务</button><button className="secondary wide" disabled={busy} onClick={() => run(async () => { const created = await mutate<Task>({ action: 'createTask', fixture: data.fixtures?.B }); await load(created.id); setSelected(created.id); reset(); setNotice('研究 B 的独立测试任务已创建。'); })}>＋ 创建研究 B 测试任务</button>
          <label>下一次准备重点<select aria-label="下一次准备重点" value={focus} onChange={e => setFocus(e.target.value)}><option value="BASIC">研究基本情况</option><option value="EXTRAPOLATION">亚组及其他人群适用边界</option><option value="UNKNOWN">暂不确定</option></select></label><button className="secondary wide" disabled={busy} onClick={() => run(async () => { const created = await mutate<Task>({ action: 'nextTask', focus, ...(task ? { taskId: task.id, budget: task.snapshot.plan.length } : {}) }); await load(created.id); setSelected(created.id); reset(); setNotice('已按当前有效内容和选题方式生成下一次准备，旧任务保留原样。'); })}>使用最新内容，准备下一次</button><div className="task-list">{data.tasks.map(t => <button key={t.id} className={`task ${selected === t.id ? 'active' : ''}`} disabled={busy} onClick={() => select(t.id)}><strong>{t.title}</strong><small>{t.status === 'CANCELED' ? '已取消' : `${t.snapshot.plan.length} 个准备考点`} · {new Date(t.createdAt).toLocaleString('zh-CN')}</small></button>)}</div>
          {task && <details><summary>为当前任务登记独立测试训练目录（可选）</summary><p className="muted">自定义研究必须明确提供目录。下面填写可用训练条目 JSON 数组，系统会检查考点、能力和证据引用；一旦登记就与该任务冻结绑定，不会从旧预测计划推断。</p><textarea aria-label="可替换训练目录 JSON" className="json" value={catalogText} onChange={e => setCatalogText(e.target.value)} placeholder='[{"contentId":"C1","version":"1","skillId":"...","coveredCapabilityIds":["..."],"evidenceIds":["..."],"status":"ELIGIBLE_TEST_ONLY"}]'/><button disabled={busy || !catalogText.trim()} onClick={() => run(async () => { await api({ action: 'registerTestCatalog', taskId: task.id, catalog: JSON.parse(catalogText) }); await load(); setNotice('训练目录已绑定当前冻结任务，可以重新运行团队改进发现。'); })}>登记并锁定测试目录</button></details>}
          <details><summary>使用另一套测试输入</summary><p className="muted">只接收测试任务资料，不能通过输入声明医学批准、演练或评分。</p><button className="secondary" onClick={() => setFixtureText(JSON.stringify(data.fixture, null, 2))}>载入可编辑模板</button><textarea aria-label="测试任务输入" className="json" value={fixtureText} onChange={e => setFixtureText(e.target.value)} /><button disabled={busy || !fixtureText.trim()} onClick={() => run(async () => { const fixture = JSON.parse(fixtureText); const t = await mutate<Task>({ action: 'createTask', fixture }); await load(t.id); setSelected(t.id); reset(); })}>建立这份输入的任务</button></details>
        </section>
        {task && <section className="card"><p className="eyebrow">当时的准备</p><h2>{task.title}</h2><p className="muted">计划已冻结。尚无关联演练或评分记录。</p>{task.snapshot.plan.map(p => { const skill = task.snapshot.codebook.skills.find(s => s.id === p.skillId)!; return <article key={p.skillId} className="plan"><h3>{p.question}</h3><p>{skill.topic} / {skill.cognitiveTask}</p><p>{skill.evidenceBoundary}</p><small>{p.rationale}</small></article>; })}<details><summary>版本与测试资料</summary><p>场景 {task.snapshot.scenarioVersion} · 策略 {task.snapshot.strategyVersion}</p>{task.snapshot.evidence.map(e => <article key={e.id}><h3>{e.title}</h3><p>{e.content}</p></article>)}<p className="muted">这些是虚构测试资料，未声明正式医学审批。</p></details>{!canceled && <button className="text-button" disabled={busy} onClick={() => run(async () => { await api({ action: 'cancelTask', taskId: task.id }); await load(); setNotice('已取消交流任务，不进行覆盖判断。'); })}>交流未发生，取消任务</button>}</section>}
      </aside><div className="content">
        {!task ? <section className="card empty"><div className="symbol">↗</div><h2>先有准备计划，再回看这次交流</h2><p>创建一个主用例任务，或选择已有任务。<br />复盘始终与当时的准备计划关联。</p></section> : <>
          {!canceled && <section className="card"><div className="heading"><h2>{editing ? `修订原文 V${editing.versions.at(-1)!.version}` : '这次交流，发生了什么？'}</h2><span className="badge">整段文字</span></div><p className="muted">记录对方的问题、你的回应和不确定之处。无需逐题填写；系统不会润色后替换原文。</p><SpeechInput disabled={busy} onText={text => { setRaw(old => old + text); setRawSource('VOICE_TRANSCRIPT'); setConfirmed(false); }}/><textarea aria-label="复盘原文" placeholder="可以从“对方问了……我当时……”开始。" value={raw} onChange={e => { setRaw(e.target.value); setConfirmed(false); }} maxLength={20000} /><div className="heading"><button className="text-button" onClick={() => { setRaw(data.sampleReflection); setConfirmed(false); }}>填入虚构测试原文</button><small>{raw.length} / 20,000</small></div><label><input type="checkbox" checked={occurred} onChange={e => setOccurred(e.target.checked)} /> 我确认测试情境中已发生交流</label><label><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} /> 我已核对原文，保留自己的表达；这不代表事实已核验</label><div className="actions"><button className="primary" disabled={busy || !raw.trim() || !confirmed || !occurred} onClick={() => run(async () => { await mutate({ action: 'saveRaw', taskId: task.id, ...(editing ? { feedbackId: editing.id } : {}), raw: { text: raw, source: rawSource, confirmed, exchangeOccurred: occurred, ...(editing ? { expectedVersion: editing.versions.at(-1)!.version } : {}) } }); await load(); reset(); setNotice('原文已保存。原文修订会使旧分析失效。'); })}>{busy ? '处理中…' : '确认并保存原文'}</button>{editing && <button className="secondary" onClick={reset}>取消修订</button>}</div><p className="footnote">无需逐题填写。语音转写或文字都先由你核对；不确定的部分可以保留。</p></section>}
          {canceled && <div className="alert">该交流任务已取消，保留历史原文，停止后续分析。</div>}
          {data.feedback?.map(f => <section className="card" key={f.id}><div className="heading"><h2>已确认原文 <small>V{f.versions.at(-1)!.version}</small></h2><span className="badge">{states[f.state]}</span></div><blockquote>{f.versions.at(-1)!.text}</blockquote><div className="actions"><button className="secondary" disabled={busy || canceled} onClick={() => { setEditing(f); setRaw(f.versions.at(-1)!.text); setConfirmed(false); setOccurred(false); window.scrollTo({ top: 220, behavior: 'smooth' }); }}>修正原文</button><button disabled={busy || canceled || (f.state === 'PROCESSING' && (f.processingLease?.expiresAt ?? 0) > Date.now())} onClick={() => run(async () => { await api({ action: 'analyze', feedbackId: f.id, expectedVersion: f.versions.at(-1)!.version }); await api({ action: 'discover' }); await load(); setNotice('复盘处理完毕。可查看分析状态，再去“我的后续练习”或“团队训练改进”。'); })}>{busy ? '处理中…' : f.state === 'FAILED' || f.state === 'PROCESSING' ? '重试模型分析' : '开始模型分析'}</button></div>
            {f.errorCode && <p className="error-text">分析未完成：{f.errorCode}。原文保留，可在配置/服务恢复后重试。</p>}
            {f.state === 'RESTRICTED' && <div className="alert">已停止向模型发送。{f.screening?.findings.map(s => <p key={s.code}>{s.label}</p>)}<small>已按测试路由送入内部接收箱，进度见上方“风险交接状态”。这不是企业正式报告。</small></div>}
            <details><summary>还有没说清楚的地方？补充说明（可跳过）</summary><p>可以补充谈的是哪份资料、对方怎么问、你当时怎么答。不记得就写不记得，不需要补全每个问题。</p><textarea aria-label={`补充说明 ${f.id}`} value={supplement[f.id] ?? ''} onChange={e => setSupplement({ ...supplement, [f.id]: e.target.value })}/><button disabled={busy || canceled || !supplement[f.id]?.trim()} onClick={() => run(async () => { await mutate({ action: 'saveRaw', taskId: task.id, feedbackId: f.id, raw: { text: f.versions.at(-1)!.text + '\n\n补充说明：' + supplement[f.id], confirmed: true, exchangeOccurred: true, expectedVersion: f.versions.at(-1)!.version } }); setSupplement({ ...supplement, [f.id]: '' }); await load(); setNotice('补充说明已单独形成新版原文，旧版保留。请重新分析。'); })}>确认补充文字并保存新版</button></details><details><summary>原文历史（{f.versions.length} 版）</summary>{f.versions.map(v => <article key={v.id}><small>V{v.version} · {new Date(v.createdAt).toLocaleString('zh-CN')}</small><blockquote>{v.text}</blockquote></article>)}</details>
            {f.analysis && <div className="analysis"><h3>准备覆盖与个人信号</h3>{f.analysis.differences.map((d, i) => <article className="difference" key={i}><div className="heading"><strong>{task.snapshot.codebook.skills.find(s => s.id === d.skillId)?.evidenceBoundary ?? '问题待澄清'}</strong><span className="badge">{coverageNames[d.coverage]}</span></div><p>{d.reason}</p>{d.missingCapabilityIds.length > 0 && <p>缺少：{d.missingCapabilityIds.map(id => task.snapshot.codebook.capabilities.find(c => c.id === id)?.description ?? id).join('、')}</p>}<p>{d.personalSignal === 'PENDING_VERIFY' ? '个人训练：自述困难，待验证。' : d.personalSignal === 'SELF_REPORTED_SUCCESS' ? '个人训练：仅有自述顺利的线索。' : '个人表现证据不足，暂不判断。'}</p>{d.performance.map((p, j) => <small key={j}>自述依据：{p.excerpt}</small>)}</article>)}{!f.analysis.differences.length && <p>未识别到足够明确的专业问题，暂不判断覆盖。</p>}<details><summary>提取、归类与原文引用</summary>{f.analysis.units.map(u => <article className="unit" key={u.id}><small>{u.types.map(t => types[t]).join(' · ')} / {u.mapping === 'CANDIDATE' ? '候选映射' : u.mapping === 'UNMAPPED' ? '未映射' : '未知'}</small><blockquote>{u.excerpt}</blockquote><p>{u.codes.join('、')}</p></article>)}</details><p className="footnote">{f.analysis.model} · {f.analysis.codebookVersion}</p>{f.analysis.limitations.map(l => <p className="footnote" key={l}>{l}</p>)}</div>}
          </section>)}
        </>}
      </div></div> : <section className="card"><p>当前为{roleNames[data.actor.role]}测试职责。上方只展示分配给该职责的风险事项；请打开“团队训练改进”查看内容审核和发布。</p></section>)}
    </>}
    <footer>模块 2 独立开发 · 仅使用虚构测试资料 · 不改模块 1 或旧演示流程</footer>
  </main>;
}
