import {useEffect,useState} from 'react';
import {readCourseBrief,readLearningCatalog,searchCourse} from './api';
import type {LessonMeta,CourseBrief,CoachMaterialBlock} from './api';
export function ContentText({value}:{value:unknown}){
 if(value==null)return null;
 if(typeof value==='string'){try{const v=JSON.parse(value);if(v&&typeof v==='object')return <ContentText value={v}/>;}catch{/* plain text */}return <p className="source-text">{value}</p>;}
 if(Array.isArray(value))return <div>{value.map((v,i)=><ContentText key={i} value={v}/>)}</div>;
 if(typeof value==='object')return <div>{Object.entries(value).map(([k,v])=><div key={k}>{typeof v==='object'&&v!==null?<ContentText value={v}/>:<p className="source-text">{String(v??'')}</p>}</div>)}</div>;
 return <span>{String(value)}</span>;
}
export default function LearningCatalog({demo,onPractice}:{demo:boolean;onPractice?:(lesson:string)=>void}){
 const [items,setItems]=useState<LessonMeta[]>([]),[selected,setSelected]=useState<CourseBrief|null>(null),[blocks,setBlocks]=useState<CoachMaterialBlock[]>([]),[query,setQuery]=useState(''),[status,setStatus]=useState(''),[busy,setBusy]=useState(false);
 async function refresh(){if(demo)return;setBusy(true);setStatus('');try{const res=await readLearningCatalog();setItems(res.lessons);if(!res.lessons.length)setStatus('课程库为空，请恢复课程资产。');}catch(e){setStatus(e instanceof Error?e.message:'课程读取失败');}finally{setBusy(false);}}
 useEffect(()=>{void refresh();},[demo]);
 async function choose(id:string){setBusy(true);setStatus('');try{const c=await readCourseBrief(id);setSelected(c);setBlocks(c.blocks||[]);setQuery('');}catch(e){setStatus(e instanceof Error?e.message:'读取失败');}finally{setBusy(false);}}
 return <section className="catalog-panel"><details><summary><strong>课程学习与原知识库</strong> · {items.length} 门</summary>{demo?<p>请登录后读取课程。</p>:<><button className="outline" disabled={busy} onClick={()=>void refresh()}>刷新课程</button><label>选择课程<select value={selected?.lesson_id||''} onChange={e=>void choose(e.target.value)}><option value="" disabled>选择后阅读完整课程</option>{items.map(l=><option key={l.id} value={l.id}>{l.title}</option>)}</select></label></>}{status&&<p className="notice">{status}</p>}{selected&&<article><h3>{selected.title}</h3><small>{selected.status} · 版本 {selected.revision?.slice(0,12)}</small><form className="studio-form" onSubmit={e=>{e.preventDefault();setBusy(true);void searchCourse(selected.lesson_id,query).then(r=>{setBlocks(r.blocks);setStatus(r.blocks.length?'':'本课程未检索到匹配段落');}).catch(e=>setStatus(e.message)).finally(()=>setBusy(false));}}><label>在本课程中检索<input value={query} onChange={e=>setQuery(e.target.value)} maxLength={300} required/></label><div className="studio-actions"><button className="outline" disabled={busy}>检索</button><button type="button" className="outline" onClick={()=>{setBlocks(selected.blocks||[]);setStatus('');}}>恢复全文</button></div></form>{blocks.map((b,i)=><details key={b.id||i} className="studio-materials"><summary>{b.title||'资料段落'}</summary><ContentText value={b.text||b.body}/><small>{b.locator}</small></details>)}<details><summary>参考来源</summary><ContentText value={selected.references}/></details><p className="minor">{selected.notice}</p><button className="primary" onClick={()=>onPractice?.(selected.lesson_id)}>用这门课程开始实时语音练习 →</button></article>}</details></section>;
}
