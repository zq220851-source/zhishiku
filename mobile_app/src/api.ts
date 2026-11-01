import type { SavedState, Staff } from './types';

const raw = import.meta.env.VITE_PLATFORM_API_URL?.trim() ?? '';
export function apiBase():string {
  // Feishu Workbench H5: same HTTPS site serves UI and /v1/mobile/* API.
  // Capacitor keeps requiring an explicit HTTPS API origin.
  if (!raw) return typeof window !== 'undefined' && window.location.protocol === 'https:' ? window.location.origin : '';
  let url:URL;
  try { url = new URL(raw); } catch { return ''; }
  const local = url.hostname === 'localhost' || url.hostname === '127.0.0.1';
  if (url.username || url.password || url.pathname !== '/' || url.search || url.hash ||
      !(url.protocol === 'https:' || (local && url.protocol === 'http:'))) return '';
  return url.origin;
}
export class ApiError extends Error { constructor(public status:number, message:string) { super(message); this.name='ApiError'; } }
export const voiceAccessToken=()=>token;
let token = ''; // memory-only bearer session; cleared on app restart
export function setAccessToken(t:string) { token=t; }
export function forgetToken() { token=''; }
export async function request<T>(path:string, method:'GET'|'POST'|'PUT'='GET', body?:unknown, timeoutMs=12000):Promise<T> {
  const base=apiBase();
  if (!base) throw new ApiError(0, '尚未设置有效 HTTPS 服务地址。请在 mobile_app/.env 中配置 VITE_PLATFORM_API_URL。');
  const requestToken=token;
  const controller=new AbortController();
  const timeout=setTimeout(()=>controller.abort(), timeoutMs);
  try {
    const response=await fetch(base+path, { method, signal:controller.signal,
      mode:'cors', credentials:'omit', redirect:'error', cache:'no-store',
      headers: { ...(body === undefined ? {} : {'Content-Type':'application/json'}),
                 ...(token ? {Authorization:`Bearer ${token}`} : {}) },
      ...(body === undefined ? {} : {body:JSON.stringify(body)}) });
    if (!response.ok) {
      let detail = `请求失败（HTTP ${response.status}）`;
      try { const result:unknown = await response.json();
        if (result && typeof result==='object' && 'detail' in result && typeof result.detail==='string') detail=result.detail;
      } catch { /* ignore non-JSON response */ }
      throw new ApiError(response.status,detail);
    }
    const result=response.status===204 ? undefined as T : await response.json() as T;
    if(token!==requestToken)throw new ApiError(401,'登录身份已变化，请重新读取');
    return result;
  } catch (e) {
    if (e instanceof ApiError) throw e;
    throw new ApiError(0, controller.signal.aborted ? '服务器连接超时' : '网络连接失败，请检查 HTTPS 域名和网络');
  } finally { clearTimeout(timeout); }
}
export async function login(username:string,password:string) {
  const data=await request<{access_token:string;user:Staff}>('/v1/mobile/auth/login','POST',{username,password});
  setAccessToken(data.access_token);
  return data.user;
}
export async function loginFeishu(code:string) {
  const data = await request<{access_token:string;user:Staff}>('/v1/mobile/auth/feishu','POST',{code},15000);
  setAccessToken(data.access_token);
  return data.user;
}
export const me=()=>request<{user:Staff}>('/v1/mobile/auth/me');
export const logout=async()=>{const previous=token;try{await request<void>('/v1/mobile/auth/logout','POST');}finally{if(token===previous)forgetToken();}};
export const readNotes=()=>request<SavedState<string>>('/v1/mobile/state/ui/personal_notes');
export const writeNotes=(value:string,expected_revision:number)=>request<{revision:number}>(
  '/v1/mobile/state/ui/personal_notes','PUT',{value,expected_revision});

export interface LessonMeta { id:string;title:string; kind?:string|null;status?:string|null;duration?:number|string|null }
export interface CourseBrief { lesson_id:string;title:string;revision?:string|null;status?:string|null;block_count?:number|null;reference_count?:number|null;notice:string;blocks?:CoachMaterialBlock[];references?:unknown[];content?:unknown }
export const readLearningCatalog=()=>request<{source:string;lessons:LessonMeta[];notice:string}>('/v1/mobile/learning/catalog');
export const readCourseBrief=(id:string)=>request<CourseBrief>('/v1/mobile/learning/courses/'+encodeURIComponent(id));

export interface IndustryDigestItem { id:string; title:string; source:string; published_at:string; kind:string; summary:string; limitations:string; review_status:string; url:string }
export interface IndustryDigest { source:'MODULE3'; mode:'live'; status:'ok'|'partial'; date:string; generated_at:string; items:IndustryDigestItem[]; notice:string }
export const readIndustryDigest=()=>request<IndustryDigest>('/v1/mobile/daily/industry','GET',undefined,30000);

// Phase 9: Module 1 employee-scoped practice. No legacy cookie, arbitrary upstream URL,
// credential management, or voice/WebRTC endpoint is exposed to mobile clients.
export interface CoachPriority { id:string; title:string; question?:string; why?:string }
export interface CoachSheet {
  id:string;visit?:{doctor?:string;goal?:string;id?:string};
  priorities?:CoachPriority[];method?:string;notice?:string;doctor?:string;forecast_status?:string;
  material?:{blocks?:CoachMaterialBlock[]};reminders?:string[];unknowns?:string[];
  evolution?:{budget:number;baseline:string[];proposed:string[];added:string[];displaced:string[];applied:{id:string;version:number}[];notice:string};
  consumed_evolution_versions?:{id:string;version:number}[];
  forecast?:{status?:string; selected_ids?:string[]; frozen_at?:number};
}
export interface CoachRun {
  id:string;title?:string;mode?:string;state?:string;revision:number;attempt?:number;sheet_id?:string;support_used?:boolean;
  transcript?:{role:string;text:string}[];review?:unknown;notice?:string;
  pending_request?:{id:string;answer:string}|null;
}
export const readCoachSheets=()=>request<{sheets:CoachSheet[]}>('/v1/mobile/coach/sheets');
export const readCoachSheet=(id:string)=>request<CoachSheet>('/v1/mobile/coach/sheets/'+encodeURIComponent(id));
export const prepareVisit=(context:{doctor:string;goal:string;facts:string;lesson_id:string;use_approved_methods?:boolean;shared_release_ids?:string[];shared_budget?:number})=>
  request<CoachSheet>('/v1/mobile/coach/prepare','POST',context,165000);
export const freezeVisit=(id:string,selected_ids:string[])=>request<CoachSheet>(
  '/v1/mobile/coach/sheets/'+encodeURIComponent(id)+'/freeze','POST',
  {selected_ids,previsit_confirmed:true},30000);
export const readCoachRuns=()=>request<{runs:CoachRun[]}>('/v1/mobile/coach/runs');
export const readCoachRun=(id:string)=>request<CoachRun>('/v1/mobile/coach/runs/'+encodeURIComponent(id));
export const startLesson=(lesson_id:string)=>request<CoachRun>(
  '/v1/mobile/coach/runs/learn','POST',{lesson_id},115000);
export const startVisitPractice=(sheet_id:string,option_id:string)=>request<CoachRun>(
  '/v1/mobile/coach/runs/visit','POST',{sheet_id,option_id},115000);
export const answerCoachRun=(run_id:string,answer:string,revision:number,request_id:string)=>request<CoachRun>(
  '/v1/mobile/coach/runs/'+encodeURIComponent(run_id)+'/answer','POST',
  {answer,revision,request_id},115000);
export const finishCoachRun=(id:string)=>request<CoachRun>(
  '/v1/mobile/coach/runs/'+encodeURIComponent(id)+'/finish','POST',{},115000);

// Restored Module 1 conversation actions. Only through authenticated platform API.
export interface CoachMaterialBlock { id?:string;title?:string;text?:string;body?:string;locator?:string }
export interface CoachSupport { material?:{blocks?:CoachMaterialBlock[]};sections?:{title:string;body:string}[] }
export const supportCoachRun=(id:string)=>request<CoachSupport>(
  '/v1/mobile/coach/runs/'+encodeURIComponent(id)+'/support','POST',{},30000);
export const retryCoachRun=(id:string)=>request<CoachRun>(
  '/v1/mobile/coach/runs/'+encodeURIComponent(id)+'/retry','POST',{},115000);

export const searchCourse=(lesson_id:string,q:string)=>request<{blocks:CoachMaterialBlock[]}>('/v1/mobile/learning/search?'+new URLSearchParams({lesson_id,q}));
