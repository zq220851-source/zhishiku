import { useEffect, useState } from 'react';
import { ApiError, readIndustryDigest } from './api';
import type { IndustryDigest } from './api';

function trustedLink(value: string): boolean {
  try { const u = new URL(value); return u.protocol === 'https:' && !!u.hostname && !u.username && !u.password; }
  catch { return false; }
}

export default function DailyIndustry({ demo }: { demo: boolean }) {
  const [digest, setDigest] = useState<IndustryDigest | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function refresh() {
    if (demo) return;
    setBusy(true); setError(''); setDigest(null);
    try { setDigest(await readIndustryDigest()); }
    catch(e) { setError(e instanceof ApiError && e.status === 503 ? '实时日报尚未连接或尚未生成，请稍后重试。' : e instanceof Error ? e.message : '读取日报失败'); }
    finally { setBusy(false); }
  }
  useEffect(() => { if (!demo) void refresh(); }, [demo]);
  return <section className="digest-panel" aria-label="行业学术日报">
    <h3>实时行业动态</h3>
    <p className="minor">只读接入模块三的实时公开来源；不使用历史样例，也不根据你的身份推断负责产品。</p>
    {demo ? <p className="notice">界面演示模式不读取真实日报。请登录测试账号。</p> : <button className="outline" disabled={busy} onClick={() => void refresh()}>{busy ? '加载实时数据…' : '刷新实时日报'}</button>}
    {error && <p className="notice" role="status">{error}</p>}
    {digest && <>
      <p className="digest-meta">{digest.date || '日期未提供'} · {digest.status === 'partial' ? '部分来源暂不可用' : '来源采集正常'} · {digest.items.length} 条行业动态</p>
      {digest.items.length === 0 && <p className="notice">当前没有可核验的实时行业条目。</p>}
      <div className="digest-items">{digest.items.map((item, i) => <article className="digest-item" key={item.id || String(i)}>
        <span className="digest-source">{item.source || '来源未提供'}{item.published_at ? ' · ' + item.published_at : ''}</span>
        <strong>{item.title}</strong>
        {item.summary && <p>{item.summary}</p>}
        {item.limitations && <p className="digest-limits">限制：{item.limitations}</p>}
        <span className="digest-review">医学审核：{item.review_status || '未审核'}</span>
        {trustedLink(item.url) && <a className="digest-link" href={item.url} target="_blank" rel="noopener noreferrer">查看原始来源 ↗</a>}
      </article>)}</div>
      <p className="caution">{digest.notice}</p>
    </>}
  </section>;
}
