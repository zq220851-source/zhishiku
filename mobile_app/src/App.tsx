import { useCallback, useEffect, useState, useRef } from 'react';
import { ApiError, apiBase, login, loginFeishu, logout, readNotes, writeNotes, forgetToken } from './api';
import { canFeishuSSO, acquireFeishuCode } from './feishuH5';
import type { Screen, Staff } from './types';
import LearningCatalog from './LearningCatalog';
import DailyWorkspace from './DailyWorkspace';
import ReviewWorkspace from './ReviewWorkspace';
import CoachStudio from './CoachStudio';
import OriginalCompanion from './OriginalCompanion';
import {prefs} from './original/src/app/prefs.js';
import './original-scoped.css';
import './restored.css';

const FEATURES = [
  {id:'coach' as Screen, icon:'✳',color:'blue',label:'准备与演练',desc:'课程表达练习、访前预测与模拟实战',section:'LEARN & PRACTICE'},
  {id:'review' as Screen,icon:'▤',color:'violet',label:'复盘与成长',desc:'原话复盘、五类资产、方法验证',section:'REVIEW & GROWTH'},
  {id:'daily' as Screen,icon:'◷',color:'green',label:'知识与前沿',desc:'学术日报、公开资料、产品学习',section:'KNOWLEDGE & INSIGHTS'},
];
const ROLE:Record<string,string>={employee:'团队成员',manager:'团队主管',medical_reviewer:'医学审核',admin:'管理员'};

export default function App() {
  const sessionEpoch=useRef(0);
  const [lessonRequest,setLessonRequest]=useState<{id:string;nonce:number;taskId?:string}>();
  const [prepareRequest,setPrepareRequest]=useState<{doctor?:string;facts:string;goal?:string;nonce:number}>();
  const [reviewSource,setReviewSource]=useState<{id:string;kind:'runs'|'sheets';nonce:number}>();
  const [staff,setStaff]=useState<Staff|null>(null);
  const [demo,setDemo]=useState(false);
  const [screen,setScreen]=useState<Screen>('coach');
  const [username,setUsername]=useState('');
  const [password,setPassword]=useState('');
  const [loading,setLoading]=useState(false);
  const [error,setError]=useState('');
  const [notes,setNotes]=useState('');
  const [revision,setRevision]=useState(0);
  const [saving,setSaving]=useState(false);
  const [message,setMessage]=useState('');
  const [recording,setRecording]=useState(false);
  useEffect(()=>{const update=(event:Event)=>setRecording((event as CustomEvent<boolean>).detail);window.addEventListener('medrep:recording',update);return()=>window.removeEventListener('medrep:recording',update);},[]);
  const [reduced,setReduced]=useState(prefs.get('motion')==='reduce');
  const isSignedIn=!!staff;
  const online=!!staff && !demo;
  const signedOut=()=>{sessionEpoch.current++;forgetToken();setRecording(false);setStaff(null);setDemo(false);setScreen('coach');setNotes('');setRevision(0);setPassword('');setLessonRequest(undefined);setPrepareRequest(undefined);setReviewSource(undefined);setError('');setMessage('');};
  const loadNotes=useCallback(async()=>{
    const epoch=sessionEpoch.current;
    try { const s=await readNotes();if(epoch!==sessionEpoch.current)return;setNotes(typeof s.value==='string' ? s.value : '');setRevision(s.revision);setError(''); }
    catch(e){if(epoch===sessionEpoch.current)setError(e instanceof Error?e.message:'读取失败');}
  },[]);
  useEffect(()=>{if(screen==='notes' && online) void loadNotes();},[screen,online,loadNotes]);
  async function doFeishuLogin(){
    setError(''); setLoading(true);
    try {
      const code = await acquireFeishuCode();
      const user = await loginFeishu(code);
      setStaff(user); setDemo(false); setScreen('coach'); setPassword('');
    } catch (e) {
      setError(e instanceof Error ? e.message : '飞书登录暂不可用，可先使用已有员工账号登录');
    } finally { setLoading(false); }
  }
  async function doLogin(ev:React.FormEvent){ ev.preventDefault();setError('');setLoading(true);
    try { const s=await login(username,password);setStaff(s);setDemo(false);setScreen('coach');setPassword('');window.scrollTo(0,0); }
    catch(e){setError(e instanceof ApiError && e.status===401?'账号或密码错误':e instanceof Error?e.message:'登录失败');}
    finally {setLoading(false);}
  }
  async function doLogout(){const pending=demo?Promise.resolve():logout();signedOut();try{await pending;}catch{/* local session already ended */}}
  async function save(){setMessage('');if(demo){setMessage('演示模式：内容仅保存在当前页面，不上传云端。');return;}
    const epoch=sessionEpoch.current;setSaving(true);try{const s=await writeNotes(notes,revision);if(epoch!==sessionEpoch.current)return;setRevision(s.revision);setMessage('已同步保存到个人云端空间');}
    catch(e){if(epoch!==sessionEpoch.current)return; if(e instanceof ApiError&&e.status===409){await loadNotes();setError('发现其他设备上的更新，已重新载入最新内容');} else setError(e instanceof Error?e.message:'保存失败'); }
    finally{setSaving(false);}
  }
  function go(next:Screen){setMessage('');setError('');setScreen(next);window.scrollTo({top:0,behavior:'instant'});}
  if(!isSignedIn){return <main className="auth-screen"><div className="auth-glow"/><div className="auth-content">
    <div className="auth-brand"><span className="brand-mark">M<span>+</span></span><span>MedRep Coach</span></div>
    <div className="auth-intro"><span className="overline">YOUR LEARNING COMPANION</span><h1>让每一次拜访<br/>都更有准备。</h1><p>AI 陪练、专业复盘与学术学习，<br/>让团队的专业成长触手可及。</p></div>
    <section className="login-card"><div className="section-top"><strong>欢迎回来</strong><span className="mini-pill">内部测试版</span></div><p>使用管理员开通的独立账号登录</p>
    <form onSubmit={doLogin} className="login-form"><label>员工账号<input autoComplete="username" value={username} onChange={e=>setUsername(e.target.value)} required placeholder="请输入员工账号"/></label>
    <label>登录密码<input autoComplete="current-password" type="password" value={password} onChange={e=>setPassword(e.target.value)} required placeholder="请输入密码"/></label>
    {error&&<p className="error" role="alert">{error}</p>}<button className="primary" disabled={loading||!apiBase()} type="submit">{loading?'正在验证…':'安全登录'} <span>→</span></button></form>
    {canFeishuSSO()&&<button type="button" className="demo-btn" disabled={loading||!apiBase()} onClick={()=>void doFeishuLogin()}>使用飞书工作台身份登录 ↗</button>}
    {!apiBase()&&<p className="notice">尚未配置云端 HTTPS 地址，真实登录暂不可用。</p>}
    <button className="demo-btn" onClick={()=>{setDemo(true);setStaff({id:'demo',display_name:'体验用户',tenant_id:'demo',role:'employee'});setError('');}}>先体验界面演示 <span>↗</span></button>
    </section><p className="auth-footer">MedRep Coach · Android / iOS · Phase 9</p></div></main>}
  const current=FEATURES.find(f=>f.id===screen)||FEATURES[0];
  return <div className="restored-shell"><main className="screen" key={staff.id}>
    <header className="app-header"><button className="brand" onClick={()=>go('coach')} aria-label="MedRep Coach，返回准备与演练"><span className="brand-mark" aria-hidden="true"/><span className="brand-name">MedRep <strong>Coach</strong></span></button><div className="header-tools"><button className="icon-button" onClick={()=>go('notes')} aria-label="学习笔记">✎</button><button className="icon-button" onClick={()=>go('account')} aria-label="账号与设置">☷</button></div></header>
    <div className="hero"><div className="hero-content"><h1>{screen==='notes'?'记下今天的收获':screen==='account'?'我的学习伙伴':current.label}</h1><p>{screen==='coach'?'读懂资料，把重点说清楚。':screen==='review'?'接着原任务，回看这次交流。':screen==='daily'?'从公开证据，发现新的线索。':staff.display_name}</p><span className="hero-dash"/></div><OriginalCompanion/></div>
    <div className="route-area">{demo&&<p className="demo-ribbon">界面演示 · 登录后连接真实业务与个人记录</p>}
    {FEATURES.map(f=><section key={f.id} hidden={screen!==f.id} aria-label={f.label}>
      {f.id==='coach'&&<><div inert={recording}><LearningCatalog demo={demo} onPractice={id=>setLessonRequest({id,nonce:Date.now()})}/></div><CoachStudio demo={demo} visible={screen==='coach'} lessonRequest={lessonRequest} prepareRequest={prepareRequest} onReview={(id,kind)=>{setReviewSource({id,kind,nonce:Date.now()});go('review');}}/></>}
      {f.id==='review'&&<ReviewWorkspace demo={demo} visible={screen==='review'} staff={staff} source={reviewSource} onPractice={(id,taskId)=>{setLessonRequest({id,taskId,nonce:Date.now()});go('coach');}}/>}
      {f.id==='daily'&&<DailyWorkspace demo={demo} onPrepare={data=>{setPrepareRequest({...data,nonce:Date.now()});go('coach');}}/>}
    </section>)}
    {screen==='notes'&&<><div className="back" onClick={()=>go('coach')}>← 返回工作台</div><div className="page-heading"><span className="overline navy">PERSONAL WORKSPACE</span><h1>我的学习笔记</h1><p>{demo?'演示模式仅在当前页面临时保留内容。':'笔记按你的员工 ID 隔离并同步到云端。'}</p></div><label className="note-label" htmlFor="notes">今日收获</label><textarea id="notes" className="note-textarea" value={notes} onChange={e=>setNotes(e.target.value)} maxLength={30000} placeholder="记录一次拜访准备要点，或一条值得复习的学术知识…"/><div className="note-meta"><span>{notes.length} / 30000 字</span><span>{online?'云端版本 '+revision:'演示模式'}</span></div>{error&&<p role="alert" className="error">{error}</p>}{message&&<p role="status" className="success">{message}</p>}<button className="primary" onClick={()=>void save()} disabled={saving}>{saving?'正在保存…':'保存学习笔记'} <span>✓</span></button></>}
    {screen==='account'&&<><div className="page-heading"><span className="overline navy">MY PROFILE</span><h1>我的账号</h1><p>管理登录状态与个人信息。</p></div><section className="profile-card"><div className="profile-avatar">{staff.display_name.slice(0,1)}</div><div><strong>{staff.display_name}</strong><p>{ROLE[staff.role]} · {demo?'演示身份':staff.tenant_id}</p></div></section><div className="setting-list"><div><span>账号模式</span><strong>{demo?'本地演示':'独立账号'}</strong></div><div><span>登录凭证</span><strong>{demo?'无':'仅保存在运行内存'}</strong></div><div><span>API 环境</span><strong>{apiBase()?'已配置':'未配置'}</strong></div></div><button className="outline danger" onClick={()=>void doLogout()}>退出登录</button></>}

    {screen==='account'&&<section className="companion-settings"><button className="outline" disabled={reduced} onClick={()=>window.dispatchEvent(new Event('medrep:replay'))}>重播原版开屏</button><label className="studio-confirm"><input type="checkbox" checked={reduced} onChange={e=>{setReduced(e.target.checked);prefs.set({motion:e.target.checked?'reduce':'system'});}}/>减少动态效果</label></section>}
    </div><nav className="bottom-nav" aria-label="三个业务模块">{FEATURES.map(f=><button key={f.id} className={'nav-item '+(screen===f.id?'is-active':'')} aria-current={screen===f.id?'page':undefined} onClick={()=>go(f.id)}><span className="nav-dash"/>{f.label}</button>)}</nav>
  </main></div>;
}
