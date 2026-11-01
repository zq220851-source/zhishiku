/* Fetch SSE with UTF-8/chunk boundaries preserved; never accept a truncated turn. */
async function eventStream(path, body, onEvent, signal) {
  const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal});
  if(!response.ok){const d=await response.json();throw new Error(d.error||`HTTP ${response.status}`);}
  if(!response.headers.get('content-type')?.includes('text/event-stream'))return response.json();
  const reader=response.body.getReader(),decoder=new TextDecoder();let buffer='',doneEvent=null;
  try{
    while(true){
      const {value,done}=await reader.read();buffer+=decoder.decode(value,{stream:!done});
      let end;
      while((end=buffer.indexOf('\n\n'))>=0){
        const block=buffer.slice(0,end);buffer=buffer.slice(end+2);
        const data=block.split('\n').filter(l=>l.startsWith('data:')).map(l=>l.slice(5).trimStart()).join('\n');
        if(!data)continue;
        const event=JSON.parse(data);if(event.type==='error')throw new Error(event.error);
        if(event.type==='done')doneEvent=event;
        onEvent(event);
      }
      if(done)break;
    }
    if(!doneEvent)throw new Error('连接中断，未收到完整结果；请检查已保留的文字。');
    return doneEvent;
  }finally{await reader.cancel().catch(()=>{});reader.releaseLock();}
}
if(typeof module!=='undefined')module.exports={eventStream};
