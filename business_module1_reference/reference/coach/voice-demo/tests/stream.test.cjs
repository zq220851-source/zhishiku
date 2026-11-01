const {test}=require('node:test');const assert=require('node:assert/strict');
const {eventStream}=require('../event-stream.js');const {LiveTranscriber,MicLoop}=require('../mic-loop.js');
test('SSE preserves Chinese split across byte chunks and rejects an unfinished stream',async()=>{
 const original=global.fetch;const events=[];
 function response(text){const bytes=new TextEncoder().encode(text);return new Response(new ReadableStream({start(c){for(const b of bytes)c.enqueue(Uint8Array.of(b));c.close();}}),{headers:{'Content-Type':'text/event-stream'}});}
 try{global.fetch=async()=>response('data: {"type":"draft","text":"医生您好"}\n\ndata: {"type":"done","text":"医生您好。"}\n\n');
 const result=await eventStream('/x',{},e=>events.push(e));assert.equal(events[0].text,'医生您好');assert.equal(result.text,'医生您好。');
 global.fetch=async()=>response('data: {"type":"draft","text":"半句"}\n\n');await assert.rejects(eventStream('/x',{},()=>{}),/连接中断/);
 }finally{global.fetch=original;}
});
test('streamed ASR drafts are visible but cannot be submitted before final confirmation',async()=>{
 let partial,resolve;const drafts=[];const t=new LiveTranscriber({transcribe:(a,s,p)=>{partial=p;return new Promise(r=>resolve=r)},onDraft:s=>drafts.push(s)});
 t.push('audio');await Promise.resolve();partial('草稿');assert.equal(drafts.at(-1),'草稿');let finished=false;const final=t.finish().then(x=>{finished=true;return x});await Promise.resolve();assert.equal(finished,false);resolve('修正后的完整转写');assert.equal(await final,'修正后的完整转写');
});
test('cancelled partial ASR cannot overwrite a later turn',async()=>{
 let partial,resolve;const drafts=[];const t=new LiveTranscriber({transcribe:(a,s,p)=>{partial=p;return new Promise(r=>resolve=r)},onDraft:s=>drafts.push(s)});
 t.push('audio');await Promise.resolve();t.cancel();partial('过期');resolve('过期');await Promise.resolve();assert.deepEqual(drafts,[]);
});
test('quick silence mode ends at 1.2 seconds, not five seconds',()=>{
 let sent=0;const loop=new MicLoop({gapMs:1200,onAudio:()=>sent++,onChunk:()=>{},onState:()=>{},onError:()=>{}});loop.enabled=true;loop.suspended=false;
 const frame=amp=>Float32Array.from({length:160},(_,i)=>Math.sin(i)*amp);
 for(let i=0;i<70;i++)loop.accept(frame(i%2?.08:.12),16000);
 for(let i=0;i<119;i++)loop.accept(frame(0),16000);assert.equal(sent,0);
 loop.accept(frame(0),16000);assert.equal(sent,1);
});
test('final audio bypasses obsolete preview, bounded at two requests',async()=>{
 const requests=[];const t=new LiveTranscriber({finalPriority:true,concurrency:1,onDraft:()=>{},transcribe:(a,s)=>new Promise((resolve,reject)=>requests.push({a,s,resolve,reject}))});
 t.push('old',{index:0,revision:1});await Promise.resolve();
 t.push('middle',{index:0,revision:2});t.push('final',{index:0,revision:3});await Promise.resolve();assert.equal(requests.length,1);
 const result=t.finish();await Promise.resolve();assert.deepEqual(requests.map(r=>r.a),['old','final']);
 requests[1].resolve('完整结果');assert.equal(await result,'完整结果');
 requests[0].resolve('过期文字');await new Promise(r=>setImmediate(r));assert.equal(t.draft(),'完整结果');
});
test('priority request failure never submits the successful old preview',async()=>{
 const requests=[];const t=new LiveTranscriber({finalPriority:true,onDraft:()=>{},transcribe:a=>new Promise((resolve,reject)=>requests.push({a,resolve,reject}))});
 t.push('old',{index:0,revision:1});await Promise.resolve();t.push('final',{index:0,revision:2});const result=t.finish();await Promise.resolve();
 requests[1].reject(new Error('final failed'));await assert.rejects(result,/final failed/);requests[0].resolve('半句话');
});
test('pause-sealed ASR windows preserve speech samples without ending the conversational turn',()=>{
 const {wavBase64}=require('../mic-loop.js');let ended=0;const chunks=new Map(),frames=[];
 const loop=new MicLoop({gapMs:5000,segmentAtPause:true,onAudio:()=>ended++,onChunk:(audio,meta)=>chunks.set(meta.index,audio),onState:()=>{},onError:()=>{}});loop.enabled=true;loop.suspended=false;
 const feed=(count,speech)=>{for(let i=0;i<count;i++){const frame=Float32Array.from({length:2048},(_,j)=>speech?Math.sin(j)*(i%2?.1:.15):0);frames.push(frame);loop.accept(frame,16000)}};
 feed(26,true);feed(4,false);assert.equal(ended,0);feed(26,true);feed(40,false);assert.equal(ended,1);assert.ok(chunks.size>=2);
 const count=audio=>{const b=Buffer.from(audio,'base64');let n=0;for(let i=44;i<b.length;i+=2)if(b.readInt16LE(i)!==0)n++;return n};
 assert.equal([...chunks.values()].reduce((n,a)=>n+count(a),0),count(wavBase64(frames,16000)));
});

test('endpoint-only capture sends no previews and preserves long speech without overlapping audio',()=>{
 const chunks=[];let ended=0;const loop=new MicLoop({endpointOnly:true,gapMs:1200,onChunk:(a,m)=>chunks.push({a,m}),onAudio:()=>ended++,onState:()=>{},onError:()=>{}});loop.enabled=true;loop.suspended=false;
 const frame=amp=>Float32Array.from({length:160},(_,i)=>Math.sin(i)*amp);
 for(let i=0;i<1800;i++)loop.accept(frame(i%2?.08:.12),16000);
 assert.equal(chunks.length,0);
 for(let i=0;i<60;i++)loop.accept(frame(0),16000);
 assert.equal(chunks.length,0);assert.equal(ended,0);
 for(let i=0;i<1600;i++)loop.accept(frame(i%2?.08:.12),16000);
 assert.equal(chunks.length,1);assert.equal(ended,0);
 for(let i=0;i<120;i++)loop.accept(frame(0),16000);
 assert.equal(chunks.length,2);assert.equal(ended,1);
 assert.deepEqual(chunks.map(c=>c.m),[{index:0,revision:1},{index:1,revision:1}]);
 const nonzero=chunks.reduce((n,c)=>{const b=Buffer.from(c.a,'base64');for(let i=44;i<b.length;i+=2)if(b.readInt16LE(i)!==0)n++;return n},0);
 const expected=3400*Array.from(frame(.08)).filter(x=>Math.abs(x*32767)>=1).length;
 assert.equal(nonzero,expected);
});
test('failed audio can be retried without retranscribing successful segments',async()=>{
 const calls=[];let fail=true;const t=new LiveTranscriber({concurrency:1,onDraft:()=>{},transcribe:async audio=>{calls.push(audio);if(audio==='second'&&fail)throw Error('HTTP 429');return audio==='first'?'医生您好。':'我下次带资料。';}});
 t.push('first',{index:0,revision:1});t.push('second',{index:1,revision:1});await assert.rejects(t.finish(),/429/);
 const saved=t.recovery();assert.equal(saved[1].audio,'second');assert.equal(saved[0].audio,null);
 t.cancel();fail=false;t.restore(saved);assert.equal(await t.finish(),'医生您好。我下次带资料。');assert.deepEqual(calls,['first','second','second']);
});
test('repeated retry failure never submits an incomplete transcript',async()=>{
 const t=new LiveTranscriber({onDraft:()=>{},transcribe:async()=>{throw Error('unavailable')}});t.push('audio');await assert.rejects(t.finish());const saved=t.recovery();t.cancel();t.restore(saved);await assert.rejects(t.finish());assert.equal(t.recovery()[0].audio,'audio');t.cancel();assert.deepEqual(t.recovery(),[]);
});
