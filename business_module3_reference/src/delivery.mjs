// Optional delivery layer. The digest is composed once; each channel adapts it.
const FEISHU_TOKEN_URL='https://accounts.feishu.cn/oauth/v3/token';
const FEISHU_MESSAGE_URL='https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id';
const tokenCache=new Map();

function line(item){
 const english=!!item.abstract&&!/[\u3400-\u9fff]/.test(item.originalTitle||item.title||'');
 const title=String(item.translation?.title||(english?'中文译文准备中':item.title)||'未命名条目').replace(/\s+/g,' ').slice(0,180);
 const status=item.approvalStatus?'｜'+item.approvalStatus:'';
 const url=String(item.url||'');
 return '• '+title+status+'\n  '+url;
}
export function formatDailyMessage(digest){
 if(!digest||!Array.isArray(digest.industry)||!Array.isArray(digest.learning))throw new Error('日报内容不完整');
 const date=digest.date||'历史样例';
 const parts=['医药前沿日报｜'+date+(digest.employee?.label?'｜'+digest.employee.label:''),'行业动态 · 全员共读',...(digest.industry.length?digest.industry.map(line):['本期暂无符合条件的新内容。']),'产品与在研学习 · 按负责产品',...(digest.learning.length?digest.learning.map(line):['本期暂无匹配的新内容。']),'内部学习，未经医学审核；在研项目及新增适应症以正式批准信息为准。'];
 const result=parts.join('\n\n');
 if(new TextEncoder().encode(result).length>12000)throw new Error('日报消息过长，请缩短篇幅');
 return result;
}
export function deliveryCapabilities(env={}){
 return {web:{status:'active'},feishu:{status:env.FEISHU_APP_ID&&env.FEISHU_APP_SECRET?'configured':'unconfigured',requires:['企业使用飞书','企业自建应用及机器人权限','员工 open_id 与产品分配表'],automatic:env.FEISHU_DELIVERY_ENABLED==='true'&&!!env.BUCKET}};
}
function validateOpenId(value){
 if(!/^ou_[A-Za-z0-9_-]{8,128}$/.test(String(value||'')))throw new Error('飞书 open_id 格式无效');
 return value;
}
async function responseJSON(response,label){
 if(!response.ok)throw new Error(label+' HTTP '+response.status);
 try{return await response.json();}catch{throw new Error(label+' 返回格式异常');}
}
async function tenantToken(env,fetcher=fetch){
 if(!env.FEISHU_APP_ID||!env.FEISHU_APP_SECRET)throw new Error('飞书企业应用凭证未配置');
 const cached=tokenCache.get(env.FEISHU_APP_ID);
 if(cached&&cached.expiresAt>Date.now()+60000)return cached.value;
 const r=await fetcher(FEISHU_TOKEN_URL,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({grant_type:'client_credentials',client_id:env.FEISHU_APP_ID,client_secret:env.FEISHU_APP_SECRET}),signal:AbortSignal.timeout(15000)});
 const data=await responseJSON(r,'飞书访问凭证');
 if(data.code!==0||!data.access_token||!Number.isFinite(data.expires_in))throw new Error('飞书访问凭证获取失败：'+(data.code??'unknown'));
 tokenCache.set(env.FEISHU_APP_ID,{value:data.access_token,expiresAt:Date.now()+data.expires_in*1000});
 return data.access_token;
}
async function dailyRequestId(date,openId){
 const bytes=new TextEncoder().encode('medrep-daily:'+date+':'+openId);
 const hash=new Uint8Array(await crypto.subtle.digest('SHA-256',bytes));
 return [...hash].slice(0,20).map(x=>x.toString(16).padStart(2,'0')).join('');
}
export async function sendFeishuDigest(digest,openId,env,fetcher=fetch){
 validateOpenId(openId);
 const content=formatDailyMessage(digest);
 const token=await tenantToken(env,fetcher);
 const uuid=await dailyRequestId(digest.date||'sample',openId);
 const body={receive_id:openId,msg_type:'text',content:JSON.stringify({text:content}),uuid};
 const r=await fetcher(FEISHU_MESSAGE_URL,{method:'POST',headers:{'Content-Type':'application/json; charset=utf-8',Authorization:'Bearer '+token},body:JSON.stringify(body),signal:AbortSignal.timeout(15000)});
 const data=await responseJSON(r,'飞书发送消息');
 if(data.code!==0||!data.data?.message_id)throw new Error('飞书发送失败：'+(data.code??'unknown'));
 return {channel:'feishu',messageId:data.data.message_id,requestId:uuid};
}
export function validateAssignments(value,products){
 if(!Array.isArray(value))throw new Error('员工分配表必须为数组');
 const marketed=new Set(products.filter(p=>p.status==='marketed').map(p=>p.id));
 const seen=new Set();
 return value.filter(row=>row?.active===true).map(row=>{
  if(typeof row.employee_id!=='string'||!row.employee_id||seen.has(row.employee_id))throw new Error('员工 ID 缺失或重复');
  seen.add(row.employee_id);
  validateOpenId(row.feishu_open_id);
  if(!Array.isArray(row.product_ids)||!row.product_ids.length||row.product_ids.some(id=>!marketed.has(String(id))))throw new Error('员工分配中含未知或在研产品');
  return {employeeId:row.employee_id,openId:row.feishu_open_id,productIds:[...new Set(row.product_ids.map(String))]};
 });
}
export async function dispatchFeishuDaily(feed,env,assemble,fetcher=fetch){
 if(env.FEISHU_DELIVERY_ENABLED!=='true')return {status:'disabled',sent:0,skipped:0};
 if(!env.BUCKET)throw new Error('云端投递需要持久存储');
 const file=await env.BUCKET.get('delivery/assignments.json');
 if(!file)return {status:'waiting_for_assignments',sent:0,skipped:0};
 const rows=validateAssignments(await file.json(),feed.pipeline?.products||[]);
 let sent=0,skipped=0;const errors=[];
 for(const row of rows){
  const digest=await assemble(feed,[],'standard',row.productIds);
  const key='delivery/sent/'+feed.date+'/'+await dailyRequestId(feed.date,row.openId)+'.json';
  if(await env.BUCKET.get(key)){skipped++;continue;}
  try{const result=await sendFeishuDigest(digest,row.openId,env,fetcher);await env.BUCKET.put(key,JSON.stringify({messageId:result.messageId,sentAt:new Date().toISOString()}),{httpMetadata:{contentType:'application/json'}});sent++;}
  catch(e){errors.push({error:String(e.message||e).slice(0,120)});}
 }
 return {status:errors.length?'partial':'ok',sent,skipped,errors};
}
