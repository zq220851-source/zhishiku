'use client';
import { useMemo, useState } from 'react';
import { evaluateLab, labCases } from '../../lib/lab-cases';
import type { LabCase } from '../../lib/lab-cases';
const names = { CONTENT: 'L2 · 补充训练场景', STRATEGY: 'L3 · 调整选题策略', PERSONAL_ONLY: '优先个人训练', INSUFFICIENT_DATA: '证据不足，暂不决策' };
export function CoreLab() {
  const cases = useMemo(labCases, []);
  const [selected, setSelected] = useState(cases[0].id);
  const [ran, setRan] = useState<string[]>([]);
  const entry = cases.find(c => c.id === selected)!;
  const current = evaluateLab(entry);
  const passedCount = cases.filter(c => ran.includes(c.id) && evaluateLab(c).passed).length;
  const run = (c: LabCase) => setRan(old => [...new Set([...old, c.id])]);
  return <section className="lab-shell" aria-label="模块 2 核心功能测试实验台">
    <div className="lab-header"><div><p className="eyebrow">CORE FUNCTION / TEST LAB</p><h2>核心判断测试台</h2><p>用两套独立的虚构研究，检查反馈能否准确分流到个人训练、场景进化或选题优化。</p></div>
      <div className="lab-score"><strong>{passedCount}<span> / {cases.length}</span></strong><small>本页面已运行且符合预期的案例</small><button className="primary" onClick={() => setRan(cases.map(c => c.id))}>运行全部 {cases.length} 项</button></div></div>
    <div className="lab-note" role="note"><strong>测试边界：</strong>这里使用人工提供的虚构复盘文字和结构化分析信号，真实运行的是模块 2 的 L2/L3 决策逻辑，<strong>不是调用 AI 分析口语</strong>。要测语义提取，请到“拜访后复盘”使用已配置的模型。</div>
    <div className="lab-layout"><aside className="lab-list"><div className="lab-list-title">研究 A · 主要终点 / 外推</div>{cases.filter(c => c.study === 'A').map(c => <CaseButton key={c.id} c={c} selected={selected} ran={ran} choose={setSelected}/>)}
      <div className="lab-list-title">研究 B · 观察窗口 / 长期边界</div>{cases.filter(c => c.study === 'B').map(c => <CaseButton key={c.id} c={c} selected={selected} ran={ran} choose={setSelected}/>)}</aside>
      <div className="lab-detail"><div className="lab-topline"><span>案例 {entry.id} · 虚构数据</span><span>{ran.includes(entry.id) ? current.passed ? '✓ 符合预期' : '✕ 与预期不符' : '待运行'}</span></div><h3>{entry.title}</h3>
        <p className="lab-heading">药代自然口述样例</p><blockquote>{entry.utterance}</blockquote>
        <div className="lab-metrics"><div><small>原准备覆盖</small><strong>{entry.coverage}</strong></div><div><small>训练目录</small><strong>{entry.catalog === 'DEFAULT' ? '有可核验目录' : entry.catalog === 'MISSING' ? '未提供' : '部分覆盖'}</strong></div><div><small>已有候选版本</small><strong>{entry.released.length ? '存在共享内容' : '无新增版本'}</strong></div></div>
        <p className="lab-heading">模块 2 实际决策</p><div className={`lab-decision ${current.passed ? 'pass' : 'fail'}`}><span className="lab-decision-icon">{current.result.kind === 'CONTENT' ? 'L2' : current.result.kind === 'STRATEGY' ? 'L3' : '—'}</span><div><strong>{names[current.result.kind]}</strong><p>{current.result.reason}</p></div></div>
        <div className="lab-check"><span>人工设定的验收预期：{names[entry.expected]}</span><small>为什么这样测：{entry.why}</small></div>
        {current.preview && <div className="lab-compare"><strong>同等题量的选题对照 · {current.preview.caseId}</strong><div className="lab-compare-cols"><div><small>旧方案选中</small><p>{current.preview.old.map(id => current.input.codebook.skills.find(s => s.id === id)?.evidenceBoundary ?? id).join('、')}</p></div><div><small>候选方案选中</small><p>{current.preview.next.map(id => current.input.codebook.skills.find(s => s.id === id)?.evidenceBoundary ?? id).join('、')}</p></div></div><small>新增覆盖：{current.preview.added.length} 项；新增遗漏：{current.preview.lost.length} 项（仅限虚构留出样例）</small></div>}
        <button className="primary lab-run" onClick={() => run(entry)}>{ran.includes(entry.id) ? '重新运行此案例' : '运行此案例'}</button>
      </div></div>
    <p className="footnote">这里的通过率是规则一致性，不是 AI 识别准确率或真实业务改善率。模块 1 的正式知识库和训练执行仍未接入。</p>
  </section>;
}
function CaseButton({ c, selected, ran, choose }: { c: LabCase; selected: string; ran: string[]; choose: (id: string) => void }) {
  return <button className={`lab-case ${selected === c.id ? 'is-selected' : ''}`} onClick={() => choose(c.id)}><span className="lab-case-id">{c.id}</span><span>{c.title}</span><span className="lab-case-result">{ran.includes(c.id) ? evaluateLab(c).passed ? '✓' : '✕' : '·'}</span></button>;
}
