'use client';
import { useState } from 'react';
import type { DiscoveryRun } from '../../lib/discovery';
import type { Actor } from '../../lib/types';
import type { EvolutionView } from '../../lib/evolution-types';
const stateName = { DRAFT: '待检查', REVIEWING: 'Agent 正在检查', BLOCKED: '有问题待处理', READY: '本项检查已完成', PUBLISHED: '已用于后续准备', RECALLED: '已撤回' };
export function EvolutionPanel({ data, discovery, actor, busy, action }: { discovery: DiscoveryRun[]; data: EvolutionView; actor: Actor; busy: boolean; action: (body: unknown) => Promise<unknown> }) {
  const [notes, setNotes] = useState<Record<string,string>>({});
  async function run(body: unknown) { try { await action(body); } catch { /* shared error banner */ } }
  return <section className="card"><p className="eyebrow">把这次发现的问题，用到下一次</p><h2>团队训练改进</h2><p>缺少训练内容，先补内容；已有内容没选到，再调整选题。个人没答好，不等于大家的训练内容一定有问题。</p>
    {actor.role === 'EMPLOYEE' && <button disabled={busy} onClick={() => run({ action: 'discover' })}>整理已完成复盘中的改进线索</button>}
    {actor.role === 'EMPLOYEE' && <button className="secondary" disabled={busy} onClick={() => run({ action: 'discoverPatterns' })}>让 AI 比较多次复盘，寻找共性和反例</button>}
    {discovery.slice(0,1).map(r => <section key={r.id}><h3>多次复盘的发现 · {r.current ? '当前资料' : '原文已更新，以下为历史候选'}</h3>{!r.patterns.length && <p>暂时没有足够线索形成模式。</p>}{r.patterns.map((p,i) => <details key={i}><summary>{p.label}（候选，未作为医学结论或发布依据）</summary><p>{p.reason}</p><p>其他解释：{p.alternatives}</p>{p.supports.map(n => <blockquote key={n}>依据：{r.observations[n].excerpt}</blockquote>)}{p.counters.map(n => <blockquote key={n}>反例：{r.observations[n].excerpt}</blockquote>)}</details>)}</section>)}
    {!data.knowledgeAvailable && <p role="alert">当前资料已停用，相关训练与发布暂停。</p>}
    {!!data.pendingDecisions?.length && <details><summary>这次没有触发共享变更的线索（{data.pendingDecisions.length}）</summary>{data.pendingDecisions.map((n,i) => <div className="plan" key={i}><strong>{n.study} · {n.skillId ?? '未映射'} · {n.status === 'INSUFFICIENT_DATA' ? '需要补充证据' : '优先个人训练'}</strong><p>{n.reason}</p></div>)}</details>}
    {!data.proposals.length && <p>还没有需要共享更新的线索。完成复盘分析后可整理，不会为了展示进化而强行改内容。</p>}
    {data.proposals.map(p => <article className="difference" key={p.id}><div className="heading"><h3>{p.kind === 'CONTENT' ? '补充训练内容' : '调整下次选题'}：{p.label}</h3><span className="badge">{stateName[p.state]}</span></div><p>{p.reason}</p>
      <details><summary>看看原话、建议和其他选择</summary>{p.sources.map((s,i) => <blockquote key={i}>{s.excerpt}<small>{s.coverage === 'FULL' ? '原计划覆盖了' : s.coverage === 'PARTIAL' ? '原计划部分覆盖' : s.coverage === 'NONE' ? '原计划未覆盖' : '原计划覆盖未知'} · {s.signal === 'PENDING_VERIFY' ? '自述有困难' : s.signal === 'SELF_REPORTED_SUCCESS' ? '自述较顺利' : '个人表现未知'}</small></blockquote>)}<h4>准备怎么练</h4><p>{p.question}</p><h4>资料支持的回答</h4><p>{p.answer || '等待资料'}</p>{p.alternatives.map(s => <p key={s}>{s}</p>)}<small>第 {p.version} 版 · 仅虚构测试用途</small></details>
      <p>医学 Agent：{p.medical ? `${p.medical.decision === 'PASS' ? '资料核对通过' : '暂不通过'}。${p.medical.reason}` : '还未检查'}</p>
      <p>培训审核：{p.training ? `${p.training.approved ? '同意训练用途' : '暂不同意'}。${p.training.reason}` : '待培训职责确认教学价值'}</p>
      <p>发布 Agent：{p.publication ? `${p.publication.decision === 'PASS' ? '检查完成' : '暂不发布'}。${p.publication.reason}` : '等待前面的条件'}</p>
      {p.kind === 'STRATEGY' && data.proposalComparisons?.[p.id] && <details><summary>本研究的新旧选题对照</summary>{data.proposalComparisons[p.id].map(c => <p key={c.caseId}>{c.partition === 'HOLDOUT' ? '留出' : '开发'} · {c.caseId}：{!c.valid ? '数据不足' : `新增命中 ${c.added.length} 项，新增遗漏 ${c.lost.length} 项`}</p>)}</details>}
      {p.checks && <details><summary>实际检查结果</summary>{p.checks.map(c => <p key={c.name}>{c.passed ? '✓' : '✕'} {c.name}</p>)}</details>}
      {p.error && <p role="alert">本次未完成：{p.error}，可检查条件后重试。</p>}
      {!['PUBLISHED','RECALLED'].includes(p.state) && <div className="actions">
        <button disabled={busy} onClick={() => run({ action: 'continueAgents', id: p.id })}>让两位 Agent 继续处理</button>
        {actor.role === 'MEDICAL_REVIEWER' && <button disabled={busy} onClick={() => run({ action: 'runMedicalAgent', id: p.id })}>让医学 Agent 查资料</button>}
        {actor.role === 'TRAINING_REVIEWER' && <><input aria-label={`培训审核理由 ${p.id}`} placeholder="说明是否适合训练，以及原因" value={notes[p.id] ?? ''} onChange={e => setNotes({ ...notes, [p.id]: e.target.value })}/><button disabled={busy || !notes[p.id]?.trim()} onClick={() => run({ action: 'trainingReview', id: p.id, hash: p.hash, approved: true, reason: notes[p.id] })}>同意训练用途</button><button className="secondary" disabled={busy || !notes[p.id]?.trim()} onClick={() => run({ action: 'trainingReview', id: p.id, hash: p.hash, approved: false, reason: notes[p.id] })}>退回并说明原因</button></>}
        {actor.role === 'PUBLISHER' && <button disabled={busy} onClick={() => run({ action: 'runPublicationAgent', id: p.id })}>让发布 Agent 检查并发布</button>}
      </div>}
    </article>)}
    <h3>已经发布的内容，后来有没有用上</h3>
    {!data.releases.length && <p>尚未发布。发布不等于有效，后面还要看实际使用和复盘。</p>}
    {data.releases.map(r => <article key={r.id} className="plan"><strong>{r.kind === 'CONTENT' ? '训练内容' : '选题方式'}：{r.label} · {r.active ? '可使用' : '已停用'}</strong><p>已被 {r.uses} 次准备选用，收到 {r.feedback} 份后续复盘，其中 {r.difficulties} 份仍报告这方面有困难。</p><small>这些记录不能直接证明改善由新版本造成。</small>{actor.role === 'PUBLISHER' && <><input placeholder="撤回原因" aria-label={`撤回版本原因 ${r.id}`} value={notes[r.id] ?? ''} onChange={e => setNotes({ ...notes, [r.id]: e.target.value })}/><button disabled={busy || !notes[r.id]?.trim()} onClick={() => run({ action: r.active ? 'recallRelease' : 'restoreRelease', id: r.id, reason: notes[r.id] })}>{r.active ? '停止使用这版' : '重新检查并恢复这版'}</button></>}</article>)}
    <details><summary>选题调整怎样比较</summary><p>新旧方式使用同一份内容、同样两项练习的测试负担；开发样例和留出样例分别记录。结果仅证明这些虚构样例下的行为。</p>{data.comparisons.map(c => <p key={c.caseId}>{c.partition === 'HOLDOUT' ? '留出检验' : '开发检验'} · {c.caseId}：{!c.valid ? '资料未齐，暂不能比较' : `新增覆盖 ${c.added.length} 项，新增遗漏 ${c.lost.length} 项`}</p>)}</details>
  </section>;
}
