/* Capture only. Energy-based voice activity detection is not a local AI model.
 * Speech recognition runs remotely in Qwen; recorded chunks are never persisted.
 */
function wavBase64(frames, sampleRate) {
  const length=frames.reduce((n,f)=>n+f.length,0),buffer=new ArrayBuffer(44+length*2),view=new DataView(buffer);
  const str=(at,s)=>{for(let i=0;i<s.length;i++)view.setUint8(at+i,s.charCodeAt(i));};
  str(0,'RIFF');view.setUint32(4,36+length*2,true);str(8,'WAVE');str(12,'fmt ');
  view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,1,true);
  view.setUint32(24,sampleRate,true);view.setUint32(28,sampleRate*2,true);view.setUint16(32,2,true);view.setUint16(34,16,true);
  str(36,'data');view.setUint32(40,length*2,true);let offset=44;
  for(const frame of frames)for(const value of frame){const n=Math.max(-1,Math.min(1,value));view.setInt16(offset,n<0?n*32768:n*32767,true);offset+=2;}
  const bytes=new Uint8Array(buffer);let binary='';
  for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));
  return btoa(binary);
}
class MicLoop {
  constructor({onAudio,onChunk,onTurnStart=()=>{},onActivity=()=>{},onState,onError,gapMs=5000,segmentAtPause=false,endpointOnly=false}){
    Object.assign(this,{onAudio,onChunk,onTurnStart,onActivity,onState,onError,gapMs,segmentAtPause,endpointOnly});this.enabled=false;this.suspended=true;
    this.stream=null;this.context=null;this.node=null;this.version=0;this.activation=0;this.preparing=null;this.resetFrames();
  }
  resetFrames(){this.frames=[];this.pre=[];this.voiced=0;this.samples=0;this.quiet=0;this.noise=0.003;this.speaking=false;this.levels=[];this.chunkHasSpeech=false;this.chunkCount=0;this.peak=0;this.segment=0;this.revision=0;this.lastSnapshot=0;}
  prepare(){
    if(this.preparing)return this.preparing;
    let timer;
    const pending=Promise.race([this.prepareDevice(),new Promise((_,reject)=>{
      timer=setTimeout(()=>reject(new Error('等待麦克风权限超时，请在浏览器中允许麦克风，或取消连续语音后使用文字。')),12000);
    })]);this.preparing=pending;
    pending.finally(()=>{clearTimeout(timer);if(this.preparing===pending)this.preparing=null;}).catch(()=>{});
    return pending;
  }
  async prepareDevice(){
    if(this.context?.state==='running'&&this.stream?.active)return;
    const version=this.version;
    // Unlock audio synchronously inside the user's Start/Microphone click.
    const Context=window.AudioContext||window.webkitAudioContext;
    const context=new Context({sampleRate:16000});this.context=context;
    const resumed=context.resume();resumed.catch(()=>{});
    const stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true,autoGainControl:true},video:false});
    if(version!==this.version){stream.getTracks().forEach(t=>t.stop());return;}
    this.stream=stream;
    try{
      await resumed;await context.audioWorklet.addModule('/pcm-worklet.js');
      if(version!==this.version)return;
      const source=context.createMediaStreamSource(stream),node=new AudioWorkletNode(context,'pcm-recorder');this.node=node;
      const silent=context.createGain();silent.gain.value=0;source.connect(node);node.connect(silent).connect(context.destination);
      node.port.onmessage=e=>this.accept(e.data,context.sampleRate);
    }catch(e){this.disable();throw e;}
  }
  enable(){this.enabled=true;return this.resume();}
  disable(){
    this.enabled=false;this.version++;this.suspend();
    this.stream?.getTracks().forEach(t=>t.stop());this.stream=null;
    const context=this.context;this.context=null;this.node=null;context?.close().catch(()=>{});this.onState('paused');
  }
  suspend(){this.activation++;this.suspended=true;this.resetFrames();}
  async resume(){
    if(!this.enabled)return;
    const version=this.version,activation=++this.activation;
    try{await this.prepare();if(version!==this.version||activation!==this.activation||!this.enabled)return;this.resetFrames();this.suspended=false;this.onState('listening');}
    catch(e){this.disable();this.onError(e.name==='NotAllowedError'?'请允许麦克风后重新开启连续对话。':'麦克风未就绪：'+e.message);}
  }
  emitChunk(rate,rotate=false){
    if(!this.chunkHasSpeech)return;
    // Keep at most 350 ms trailing silence; never send five seconds of empty audio.
    const trim=Math.max(0,Math.floor((this.quiet-350)*rate/1000));
    let keep=Math.max(0,this.samples-trim),frames=[];
    for(const f of this.frames){if(keep<=0)break;frames.push(f.subarray(0,keep));keep-=f.length;}
    const length=frames.reduce((n,f)=>n+f.length,0);
    if(length<rate*.25)frames.push(new Float32Array(Math.ceil(rate*.25)-length));
    const audio=wavBase64(frames,rate);
    this.chunkHasSpeech=false;this.chunkCount++;this.lastSnapshot=this.samples;
    if(this.onChunk)this.onChunk(audio,{index:this.segment,revision:++this.revision});else this.onAudio(audio);
    if(rotate){this.frames=[];this.samples=0;this.lastSnapshot=0;this.segment++;this.revision=0;}
  }
  accept(frame,rate){
    if(!this.enabled||this.suspended)return;
    const ms=frame.length/rate*1000,rms=Math.sqrt(frame.reduce((n,v)=>n+v*v,0)/frame.length);
    // Learn steady background even after speech begins. The previous detector froze
    // its noise floor for the whole utterance, so a fan could prevent every endpoint.
    this.levels.push(rms);while(this.levels.length>Math.ceil(1100/ms))this.levels.shift();
    if(this.levels.length>=Math.ceil(900/ms)){
      const avg=this.levels.reduce((a,b)=>a+b,0)/this.levels.length;
      const spread=Math.sqrt(this.levels.reduce((a,b)=>a+(b-avg)**2,0)/this.levels.length);
      if(spread<Math.max(.001,avg*.12))this.noise=avg;
    }
    this.peak=Math.max(rms,this.peak*.995);
    const voiced=rms>Math.max(.008,this.noise*2.5,this.speaking?this.peak*.28:0);
    if(!this.speaking){
      this.pre.push(frame);while(this.pre.length>Math.max(4,Math.ceil(180/ms)+1))this.pre.shift();
      this.onActivity({level:Math.min(1,rms*12),quietMs:0,speaking:false});
      if(!voiced){this.voiced=0;return;}
      this.voiced+=ms;if(this.voiced<180)return;
      this.speaking=true;this.frames=[...this.pre];this.samples=this.frames.reduce((n,f)=>n+f.length,0);
      this.onTurnStart();this.onState('speaking');
    }else{this.frames.push(frame);this.samples+=frame.length;}
    if(voiced)this.chunkHasSpeech=true;
    this.quiet=voiced?0:this.quiet+ms;
    this.onActivity({level:Math.min(1,rms*12),quietMs:this.quiet,speaking:true});
    if(this.quiet>=this.gapMs){
      this.emitChunk(rate);this.suspend();if(this.onChunk)this.onAudio();
    }else if(this.onChunk&&this.samples>=rate*24){
      this.emitChunk(rate,true);
    }else if(!this.endpointOnly&&this.onChunk&&this.chunkHasSpeech&&
      ((this.quiet>=350&&this.samples>=rate*.25)||
       (this.samples-this.lastSnapshot>=rate*3&&(!this.segmentAtPause||this.lastSnapshot===0)))){
      // Send a growing context window, not isolated syllables. Newer recognition
      // replaces older draft text; the latest snapshot becomes the submitted text.
      // Dedicated ASR: seal a >=3s window at an acoustic pause. Keep the
      // conversational turn open; only the selected silence gap submits it.
      // This avoids repeatedly uploading the entire growing utterance.
      this.emitChunk(rate,this.segmentAtPause&&this.quiet>=350&&this.samples>=rate*3);
    }
  }
}
/* Ordered cloud transcription: concurrent requests may finish out of order.
 * Never submit an incomplete transcript after a failed or cancelled segment. */
class LiveTranscriber {
  constructor({transcribe,onDraft,onError=()=>{},concurrency=3,finalPriority=false}){
    Object.assign(this,{transcribe,onDraft,onError,concurrency,finalPriority});this.reset();
  }
  reset(){
    this.controller?.abort();this.controller=new AbortController();this.version=(this.version||0)+1;
    this.parts=[];this.queue=[];this.running=new Set();this.finalizing=false;
  }
  cancel(){this.reset();}
  push(audio,{index=this.parts.length,revision=1}={}){
    const prior=this.parts[index];
    const part={text:prior?.text??null,audio,index,revision,textRevision:prior?.textRevision??0,error:null,pending:true};
    this.parts[index]=part;
    this.queue=this.queue.filter(p=>p.index!==index);this.queue.push(part);this.pump();
  }
  draft(){return this.parts.map(p=>p.partial??(p.text===null?'…':p.text)).join('');}
  pump(){
    const version=this.version,signal=this.controller.signal;
    // One extra slot only after endpoint confirmation. Never queue final audio
    // behind an obsolete preview, and never exceed two requests in priority mode.
    const limit=this.finalPriority?(this.finalizing?2:1):this.concurrency;
    while(this.running.size<limit&&this.queue.length){
      const part=this.queue.shift();
      const task=Promise.resolve().then(()=>version===this.version?this.transcribe(part.audio,signal,text=>{if(version===this.version&&this.parts[part.index]===part){part.partial=text;this.onDraft(this.draft());}}):'').then(text=>{
        if(version!==this.version)return;
        const latest=this.parts[part.index];
        if(!text.trim()&&latest.text?.trim()){if(latest===part)throw new Error('云端未完整识别这段发言，请检查转写后重试');return;}
        if(latest===part){part.partial=null;part.pending=false;}
        if(part.revision>latest.textRevision){latest.text=text.trim();latest.textRevision=part.revision;this.onDraft(this.draft());}
      }).catch(e=>{
        if(version===this.version&&this.parts[part.index]===part){part.error=e;part.pending=false;this.onError(e);}
      }).finally(()=>{
        if(!part.error)part.audio=null;if(version===this.version){this.running.delete(task);this.pump();}
      });
      this.running.add(task);
    }
  }
  recovery(){
    return this.parts.map(p=>({index:p.index,revision:p.revision,text:p.text,
      textRevision:p.textRevision,audio:p.error?p.audio:null,failed:!!p.error}));
  }
  restore(parts){
    this.reset();
    for(const p of parts){
      if(p.failed){if(!p.audio)throw new Error('失败录音已释放，请重新说话');this.push(p.audio,{index:p.index,revision:p.revision});}
      else this.parts[p.index]={...p,pending:false,error:null};
    }
  }
  async finish(){
    const version=this.version;
    this.finalizing=true;this.pump();
    while(this.parts.some(p=>p.pending)){
      await Promise.race([...this.running]);if(version!==this.version)return null;
    }
    const failed=this.parts.find(p=>p.error);if(failed)throw failed.error;
    return this.parts.map(p=>p.text||'').join('');
  }
}
if(typeof module!=='undefined')module.exports={MicLoop,wavBase64,LiveTranscriber};
