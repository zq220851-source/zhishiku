'use client';
import { useState } from 'react';
import type { Actor } from '../../lib/types';
import type { Attempt, LearningDashboard } from '../../lib/learning-types';
const purposes = { VERIFY: '确认性练习', RETEST: '换一种问法复测', RETENTION: '间隔复查', TRANSFER: '压力情境验证' };
const states = { UNVERIFIED: '待实际验证', NEEDS_PRACTICE: '需要针对练习', IMPROVING: '已有改善证据' };
const causeLabels = { KNOWLEDGE_UNCERTAINTY: '自述知识/证据理解不确定', BOUNDARY_OVERSTATEMENT: '自述表达过满', FOLLOW_UP_BLOCK: '自述现场追问解释卡住' };
export function LearningPanel({ actor, data, busy, action }: { actor: Actor; data: LearningDashboard; busy: boolean; action: (body: unknown) => Promise<unknown> }) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [message, setMessage] = useState('');
  async function perform(body: unknown) { setMessage(''); try { const result = await action(body) as Attempt; if (result?.state === 'FAILED') setMessage(`本次评价未完成（${result.errorCode}），答案已保留，可以重试。`); } catch { /* Parent displays the error and preserves drafts. */ } }
  if (!['EMPLOYEE', 'TRAINING_REVIEWER'].includes(actor.role)) return null;
  return <section className="card learning"><p className="eyebrow">L1 · 个人能力长期追踪</p><h2>这次练完，还会安排下一次验证</h2><p>自述只提供线索。实际作答后，按能力与情境分别记录表现；一次答对不等于永久掌握。</p>
    <p className="footnote">虚构测试规则：复查间隔 7 天。题目来自有限模板；换问法不代表独立题库验证。当前不用于正式员工评分。</p>
    {actor.role === 'EMPLOYEE' && <div className="actions"><button disabled={busy} onClick={() => perform({ action: 'syncLearning' })}>从已有复盘同步训练</button><button disabled={busy} className="secondary" onClick={() => perform({ action: 'advanceLearningClock', days: 7 })}>测试：推进 7 天</button></div>}
    <p className="muted">测试时间已推进 {data.simulatedDays} 天。到期只表示需要新观察，不自动判定退步。</p>{message && <p role="status">{message}</p>}
    <section className="plan"><h3>复盘发现的个人训练线索</h3><p className="muted">以下内容逐字来自本人复盘；“待澄清”不会自动变成练习或个人成绩。旧原文的历史会保留，但不会作为新的训练依据。</p>
      {!data.needs.length && <p>目前还没有可引用的个人线索。</p>}
      {data.needs.map(n => <article className="unit" key={n.needId}>
        <small>{n.status === 'AWAITING_CONFIRMATION' ? '待澄清，不自动安排训练' : n.status === 'SOURCE_STALE' ? '旧版来源，停止使用' : n.status === 'FOLLOW_UP' ? '已有练习改善证据，待后续复查' : '有待验证的专项需求'} · 知识版本：{n.knowledgeVersion}</small>
        <blockquote>{n.observedProblem}</blockquote><p>{n.reason}</p>
        {n.indicators?.length ? <p>这次提取的困难线索：{n.indicators.map((i, index) => <span key={`${i.kind}-${index}`}>{index ? '；' : ''}{causeLabels[i.kind]}（原话：“{i.quote}”）</span>)}。这只是自述，不是能力评分。</p> : <p className="muted">困难成因尚无法确定；先验证能力，不推断原因。</p>}
        {n.targetCapabilityIds.length > 0 && <p className="muted">拟验证能力：{n.targetCapabilities.map(c => c.description).join('、')}（尚非正式能力评价）</p>}
      </article>)}
    </section>
    {!data.profiles.length && <p>完成复盘分析后，这里会出现有可靠问答关系的专项练习；关系不明的线索留在上方等待澄清。</p>}
    {data.profiles.map(p => <article className="difference" key={p.id}><div className="heading"><h3>{p.label}</h3><span className="badge">{p.context === 'NORMAL' ? '常规情境' : '压力情境'} · {states[p.state]}</span></div><p>{p.reason}</p><small>{p.sourceCount} 条当前复盘线索 · {p.freshness === 'DUE' ? '已到复查时间' : p.freshness === 'CURRENT' ? '已有近期观察' : '尚无明确练习评价'}</small>
      {p.next && <section className="plan"><h3>下一步：{purposes[p.next.purpose]}</h3><p><strong>为什么练这道题：</strong>{p.next.trainingReason}</p><p>{p.next.question}</p><p className="muted">{!p.active ? '来源已变化，本项训练暂停。' : p.next.dueAt > data.now ? '尚未到期，可用上方按钮推进测试时间。' : '现在可以练习。'}</p>
        {actor.role === 'EMPLOYEE' && <><textarea aria-label={`练习作答：${p.label}（${p.context}）`} value={answers[p.next.id] ?? ''} maxLength={12000} placeholder="写下你实际会如何回答。模型会逐项给出引用和原因。" onChange={e => setAnswers({ ...answers, [p.next!.id]: e.target.value })} /><button disabled={busy || !p.active || p.next.dueAt > data.now || !answers[p.next.id]?.trim()} onClick={() => perform({ action: 'submitLearningAnswer', exerciseId: p.next!.id, answer: answers[p.next!.id] })}>{busy ? '评价中…' : '提交练习，查看反馈'}</button></>}
      </section>}
      <details open={p.attempts.length > 0}><summary>作答和评价记录（{p.attempts.length}）</summary>{p.attempts.map(a => <article className="unit" key={a.id}><small>{new Date(a.submittedAt).toLocaleString('zh-CN')}（含测试时间偏移） · {a.state === 'RETRACTED' ? '评价已撤回，保留历史' : a.state === 'FAILED' ? '评价失败，可重试' : a.state === 'PROCESSING' ? '正在评价' : '评价完成'}</small><blockquote>{a.answer}</blockquote>{a.grade && <><p>{a.grade.summary}</p>{a.grade.criteria.map(c => <p key={c.id}><strong>{c.result === 'SATISFIED' ? '已体现' : c.result === 'GAP' ? '尚有缺项' : '暂无法判断'}</strong>：{c.reason}{c.quote && <q> {c.quote}</q>}</p>)}</>}{a.retractionReason && <p>撤回原因：{a.retractionReason}</p>}{actor.role === 'TRAINING_REVIEWER' && a.state === 'COMPLETED' && <><input aria-label={`撤回原因 ${a.id}`} placeholder="填写评价有误的具体原因" value={reasons[a.id] ?? ''} onChange={e => setReasons({ ...reasons, [a.id]: e.target.value })}/><button disabled={busy || !reasons[a.id]?.trim()} onClick={() => perform({ action: 'retractLearningAttempt', attemptId: a.id, reason: reasons[a.id] })}>撤回这次评价</button></>}</article>)}</details>
    </article>)}
    <details><summary>下一轮训练将读取什么</summary><p>下列需求已在本模块生成；模块 1 的实际接收接口尚未对接。</p>{data.profiles.filter(p => p.active && p.next).map(p => <p key={p.id}>{p.label} · {p.context === 'NORMAL' ? '常规' : '压力'} · {purposes[p.next!.purpose]} · {p.next!.dueAt <= data.now ? '当前待练' : '等待复查'}</p>)}</details>
  </section>;
}
