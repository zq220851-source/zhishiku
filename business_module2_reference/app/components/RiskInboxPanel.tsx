'use client';
import { useState } from 'react';
import type { Actor, RiskDetail, RiskState, RiskSummary } from '../../lib/types';
import { roleNames } from '../../lib/roles';
const stateNames: Record<RiskState, string> = { OPEN: '待接收', RECEIVED: '已确认接收', IN_PROGRESS: '处理中', RESOLVED: '内部处理已结束' };
const findingNames: Record<string, string> = { SPECIAL_REPORT: '安全性/质量报告线索', IDENTIFIER: '身份或联系方式', PATIENT: '患者身份线索', AUTHORIZATION: '资料授权线索' };
export function RiskInboxPanel({ actor, risks, busy, onChange, onError }: {
  actor: Actor; risks: RiskSummary[]; busy: boolean;
  onChange: (risk: RiskSummary, state: RiskState, note?: string) => Promise<void>;
  onError: (message: string) => void;
}) {
  const [detail, setDetail] = useState<RiskDetail>(); const [loading, setLoading] = useState(false); const [note, setNote] = useState('');
  async function open(id: string) {
    setLoading(true);
    try {
      const response = await fetch(`/api/module2?riskId=${encodeURIComponent(id)}`, { cache: 'no-store' });
      const value = await response.json(); if (!response.ok) throw new Error(value.error?.message ?? '读取失败。'); setDetail(value.data); setNote('');
    } catch (error) { onError(error instanceof Error ? error.message : '读取失败。'); }
    finally { setLoading(false); }
  }
  const selected = risks.find(r => r.id === detail?.id);
  return <section className="card risk-inbox" aria-label="内部风险接收箱">
    <div className="heading"><h2>{actor.role === 'EMPLOYEE' ? '风险交接状态' : '内部风险接收箱'}</h2><span className="badge">{risks.length} 项 · {roleNames[actor.role]}</span></div>
    <p className="muted">仅验证内部测试交接，不代替企业正式报告。结束处理不会自动解除原文隔离。</p>
    {!risks.length ? <p className="muted">{actor.role === 'EMPLOYEE' ? '暂无需交接的复盘。' : '当前职责没有待处理事项。'}</p> : <div className="risk-list">{risks.map(risk => <article className="difference" key={risk.id}>
      <div className="heading"><strong>{risk.findingCodes.map(c => findingNames[c] ?? c).join('、')}</strong><span className="badge">{stateNames[risk.state]}</span></div>
      <p>复盘原文 V{risk.rawVersion} → {roleNames[risk.recipientRole]}</p>
      <small>事项 {risk.id.slice(0, 8)} · {new Date(risk.createdAt).toLocaleString('zh-CN')}</small>
      {actor.role !== 'EMPLOYEE' && <button className="secondary" disabled={loading || busy} onClick={() => open(risk.id)}>查看并处理事项</button>}
    </article>)}</div>}
    {actor.role !== 'EMPLOYEE' && detail && selected && <section className="risk-detail" aria-label="风险处理详情">
      <div className="heading"><h3>事项 {detail.id.slice(0, 8)} · 原文 V{detail.rawVersion}</h3><button className="text-button" onClick={() => setDetail(undefined)}>关闭详情</button></div>
      {detail.superseded && <p className="alert">这是一份历史原文的风险事项。员工已修订原文，本事项仍需独立处理。</p>}
      <blockquote>{detail.rawText}</blockquote>
      <p>当前状态：{stateNames[selected.state]} · 事项版本 {selected.revision}</p>
      {selected.state !== 'RESOLVED' && <><textarea aria-label="风险处理说明" maxLength={2000} placeholder="记录接收/处理情况；结束处理时必须填写结果。仅使用虚构信息。" value={note} onChange={event => setNote(event.target.value)} /><div className="actions">
        <button disabled={busy || loading || (selected.state === 'IN_PROGRESS' && !note.trim())} onClick={async () => {
          const next: Partial<Record<RiskState, RiskState>> = { OPEN: 'RECEIVED', RECEIVED: 'IN_PROGRESS', IN_PROGRESS: 'RESOLVED' };
          const target = next[selected.state]; if (!target) return;
          try { await onChange(selected, target, note); await open(selected.id); } catch { /* Parent displays the controlled error. */ }
        }}>{selected.state === 'OPEN' ? '确认接收' : selected.state === 'RECEIVED' ? '开始处理' : '记录结果并结束处理'}</button>
      </div></>}
      <details open><summary>分流与处理记录</summary>{detail.history.map((entry, i) => <p key={i}><strong>{entry.type === 'ROUTED' ? '已分流' : stateNames[entry.type]}</strong> · {roleNames[entry.role]} · {new Date(entry.createdAt).toLocaleString('zh-CN')}<br />{entry.note}</p>)}</details>
    </section>}
  </section>;
}
