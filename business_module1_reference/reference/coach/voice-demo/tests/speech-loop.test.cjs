const {test}=require('node:test');const assert=require('node:assert/strict');
const {SpeechLoop}=require('../speech-loop.js');const {radarMarkup}=require('../radar.js');
const wait=ms=>new Promise(r=>setTimeout(r,ms));
function harness(){const recs=[],sent=[],drafts=[],errors=[];
 class Recognition{constructor(){recs.push(this)}start(){this.onstart?.()}abort(){this.onend?.()}}
 const loop=new SpeechLoop({Recognition,onDraft:t=>drafts.push(t),onUtterance:t=>sent.push(t),onState:()=>{},onError:e=>errors.push(e),gapMs:20});
 const result=(text,final=true)=>loop.rec.onresult({resultIndex:0,results:[Object.assign([{transcript:text}],{isFinal:final})]});
 return {loop,recs,sent,drafts,errors,result};}
test('hands-free successive turns resume without a second enable click',async()=>{
 const h=harness();h.loop.enable();h.result('您好。');await wait(35);assert.deepEqual(h.sent,['您好。']);assert.equal(h.loop.suspended,true);
 h.loop.resume();h.result('我带来了资料。');await wait(35);assert.deepEqual(h.sent,['您好。','我带来了资料。']);h.loop.disable();
});
test('brief pauses merge final chunks; interim speech cancels pending send',async()=>{
 const h=harness();h.loop.enable();h.result('第一句。');h.result('继续说',false);await wait(35);assert.equal(h.sent.length,0);
 h.result('继续说完。');await wait(35);assert.deepEqual(h.sent,['第一句。继续说完。']);h.loop.disable();
});
test('playback and timeout discard stale recognition events',async()=>{
 const h=harness();h.loop.enable();const old=h.loop.rec;h.result('未发送');h.loop.suspend();
 old.onresult({resultIndex:0,results:[Object.assign([{transcript:'医生自己的声音'}],{isFinal:true})]});await wait(35);assert.equal(h.sent.length,0);
 h.loop.resume();h.result('时间到前草稿');h.loop.disable();await wait(35);assert.equal(h.sent.length,0);
});
test('recognition service end restarts; permission denial does not loop',async()=>{
 const h=harness();h.loop.enable();h.loop.rec.onend();await wait(330);assert.equal(h.recs.length,2);
 h.loop.rec.onerror({error:'not-allowed'});assert.equal(h.loop.enabled,false);assert.equal(h.errors.length,1);h.loop.disable();
});
test('radar preserves NA as a missing axis instead of a zero point',()=>{
 const dimensions=Array.from({length:6},(_,i)=>({id:'D'+(i+1),rating:i===3?'NA':i%3}));
 const svg=radarMarkup(dimensions);assert.match(svg,/NA · 未评分/);assert.equal((svg.match(/<circle /g)||[]).length,5);
 assert.ok(!svg.includes('data-dimension="D4"'));assert.match(svg,/data-score-area="true"/);
 assert.equal((svg.match(/data-score-edge="gap"/g)||[]).length,1);
 const area=svg.match(/data-score-area="true" points="([^"]+)"/)[1];assert.equal(area.split(' ').length,5);
 dimensions[3].rating=1;const complete=radarMarkup(dimensions);assert.equal((complete.match(/data-score-edge="rated"/g)||[]).length,6);assert.ok(!complete.includes('data-score-edge="gap"'));
 dimensions.forEach((d,i)=>d.rating=i<2?1:'NA');assert.ok(!radarMarkup(dimensions).includes('data-score-area="true"'));
});
const {MicLoop,wavBase64}=require('../mic-loop.js');
test('API capture emits PCM WAV after speech and silence; playback/timeout capture nothing',()=>{
 const audio=[],states=[];const loop=new MicLoop({onAudio:a=>audio.push(a),onState:s=>states.push(s),onError:()=>{},gapMs:200});
 loop.enabled=true;loop.suspended=false;const quiet=new Float32Array(2048),speech=new Float32Array(2048).fill(.08);
 for(let i=0;i<8;i++)loop.accept(quiet,16000);assert.equal(audio.length,0);
 for(let i=0;i<5;i++)loop.accept(speech,16000);for(let i=0;i<3;i++)loop.accept(quiet,16000);
 assert.equal(audio.length,1);const wav=Buffer.from(audio[0],'base64');assert.equal(wav.toString('ascii',0,4),'RIFF');assert.equal(wav.readUInt32LE(24),16000);assert.equal(wav.readUInt16LE(22),1);
 assert.equal(loop.suspended,true);for(let i=0;i<6;i++)loop.accept(speech,16000);assert.equal(audio.length,1);
 loop.disable();assert.equal(loop.enabled,false);
});
test('WAV encoder clips samples and preserves recording sample rate',()=>{
 const wav=Buffer.from(wavBase64([new Float32Array([-2,0,2])],48000),'base64');assert.equal(wav.readUInt32LE(24),48000);assert.equal(wav.readInt16LE(44),-32768);assert.equal(wav.readInt16LE(48),32767);
});
const {LiveTranscriber}=require('../mic-loop.js');
function micHarness(){
 const chunks=[],activity=[];let ended=0;
 const loop=new MicLoop({onChunk:x=>chunks.push(x),onAudio:()=>ended++,onState:()=>{},onError:()=>{},onActivity:x=>activity.push(x)});
 loop.enabled=true;loop.suspended=false;
 const frames=(ms,amplitude)=>{for(let t=0;t<ms;t+=10)loop.accept(new Float32Array(160).fill(typeof amplitude==='function'?amplitude(t):amplitude),16000);};
 const talk=ms=>frames(ms,t=>.055+.035*Math.sin(t/67)**2);
 return {loop,chunks,activity,frames,talk,get ended(){return ended;}};
}
test('5 seconds of silence ends exactly once; speaking again at 4.9s resets the countdown',()=>{
 const h=micHarness();h.talk(900);h.frames(4900,0);assert.equal(h.ended,0);
 h.talk(500);h.frames(4990,0);assert.equal(h.ended,0);h.frames(10,0);assert.equal(h.ended,1);
 assert.equal(h.loop.suspended,true);h.frames(6000,0);assert.equal(h.ended,1);
});
test('live chunks start during speech; a 40-second utterance is not sent prematurely',()=>{
 const h=micHarness();h.talk(40000);assert.ok(h.chunks.length>=6);assert.equal(h.ended,0);
 for(const audio of h.chunks)assert.ok((Buffer.from(audio,'base64').length-44)/32000<=24.1);
 h.frames(5000,0);assert.equal(h.ended,1);
});
test('steady fan noise above the old fixed threshold does not keep the turn open',()=>{
 const h=micHarness();h.frames(2000,.019); // acquire the background floor
 h.talk(2000);h.frames(4990,.019);assert.equal(h.ended,0);
 h.frames(10,.019);assert.equal(h.ended,1);
});
test('out-of-order cloud results show drafts but submit in recording order only after finish',async()=>{
 const pending=[],drafts=[];const c=new LiveTranscriber({transcribe:()=>new Promise(r=>pending.push(r)),onDraft:t=>drafts.push(t)});
 c.push('first');c.push('second');await wait(0);pending[1]('第二句。');await wait(0);
 assert.equal(drafts.at(-1),'…第二句。');pending[0]('第一句。');
 assert.equal(await c.finish(),'第一句。第二句。');
});
test('failed recognition cannot silently submit only the successful parts',async()=>{
 const c=new LiveTranscriber({transcribe:async a=>{if(a==='bad')throw new Error('ASR unavailable');return '已识别';},onDraft:()=>{}});
 c.push('good');c.push('bad');await assert.rejects(c.finish(),/ASR unavailable/);
});
test('cancelled old transcription cannot overwrite the next microphone turn',async()=>{
 let resolve;const drafts=[];const c=new LiveTranscriber({transcribe:()=>new Promise(r=>resolve=r),onDraft:t=>drafts.push(t)});
 c.push('old');await wait(0);const finished=c.finish();c.cancel();resolve('旧内容');
 assert.equal(await finished,null);assert.deepEqual(drafts,[]);
});

test('cumulative snapshots replace drafts rather than duplicating earlier words',async()=>{
 const pending=[],drafts=[];const c=new LiveTranscriber({transcribe:()=>new Promise(r=>pending.push(r)),onDraft:t=>drafts.push(t)});
 c.push('first',{index:0,revision:1});await wait(0);pending[0]('您好');await wait(0);
 c.push('full',{index:0,revision:2});await wait(0);pending[1]('您好，今天想请教一个问题。');
 assert.equal(await c.finish(),'您好，今天想请教一个问题。');assert.equal(drafts[0],'您好');
});
test('stale snapshot cannot replace a more recent complete transcript',async()=>{
 const pending=[];const c=new LiveTranscriber({transcribe:()=>new Promise(r=>pending.push(r)),onDraft:()=>{}});
 c.push('old',{index:0,revision:1});c.push('new',{index:0,revision:2});await wait(0);
 pending[1]('完整句');await wait(0);pending[0]('旧半句');assert.equal(await c.finish(),'完整句');
});

test('an empty later snapshot cannot erase already recognized speech and be auto-submitted',async()=>{
 const c=new LiveTranscriber({transcribe:async a=>a==='first'?'您好医生':'',onDraft:()=>{}});
 c.push('first',{index:0,revision:1});await c.finish();c.push('blank',{index:0,revision:2});
 await assert.rejects(c.finish(),/未完整识别/);assert.equal(c.draft(),'您好医生');
});
