// Read the actual module-1 source corpus. Missing data never becomes a persona.
export async function readModule1(env,path,fetcher=fetch){
 const base=env.MODULE1_BASE_URL;
 const u=new URL(base);
 if(u.protocol!=='http:'||u.hostname!=='127.0.0.1')throw Error('模块一知识服务必须在本机');
 const r=await fetcher(base+path,{signal:AbortSignal.timeout(30000)});
 if(!r.ok)throw Error('模块一知识服务读取失败：HTTP '+r.status);
 return r.json();
}
export async function connectedConfig(env,products,topics,sources,fetcher=fetch){
 const corpus=await readModule1(env,'/api/knowledge/catalog',fetcher);
 if(corpus.system!=='MODULE1'||corpus.mode!=='SOURCE_CORPUS')throw Error('知识库来源不匹配');
 const norm=s=>String(s).replace(/[®\s]/g,'');
 const catalog=corpus.products.flatMap(p=>{
  const matched=products.find(x=>norm(x.name)===norm(p.brand));
  return matched?[{...matched,module1ProductId:p.product_id,sourceStatus:p.review_status,sourceReference:p.reference_source}]:[];
 });
 return {sourceMode:'MODULE1',products:catalog,pipeline:products.filter(p=>p.status==='investigational'),topics,sources,profile:null,
  knowledge:{version:corpus.version,courses:corpus.courses,products:corpus.products,questions:corpus.questions,questionDrafts:corpus.questionDrafts||[],sourceAsOf:corpus.sourceAsOf,claims:corpus.claims,sources:corpus.sources},
  employeeProfileStatus:'NOT_CONNECTED',notice:corpus.notice,
  timeZone:'Asia/Shanghai',refreshTime:'08:00',scheduleEnabled:false};
}
