/* Streaming transport: microphone PCM -> local bridge -> Bailian.
 * Keys never enter WebSocket URLs or browser storage. */
class PCM16Encoder {
  constructor(rate){this.ratio=rate/16000;this.phase=0;this.sum=0;this.count=0;}
  encode(frame){
    const values=[];
    for(const x of frame){this.sum+=x;this.count++;this.phase++;
      if(this.phase>=this.ratio){const v=Math.max(-1,Math.min(1,this.sum/this.count));values.push(v<0?v*32768:v*32767);this.phase-=this.ratio;this.sum=0;this.count=0;}}
    const bytes=new ArrayBuffer(values.length*2),view=new DataView(bytes);
    values.forEach((v,i)=>view.setInt16(i*2,v,true));return bytes;
  }
}
class StreamingMicLoop extends MicLoop {
  constructor(options){super({...options,onAudio:()=>{}});Object.assign(this,options);this.socket=null;}
  suspend(){this.socket?.close();this.socket=null;clearTimeout(this.finalTimer);super.suspend();}
  async resume(){
    if(!this.enabled||this.socket)return;
    const version=this.version,activation=++this.activation;
    this.onState('connecting');
    try{
      await this.prepare();if(version!==this.version||activation!==this.activation||!this.enabled)return;
      this.resetFrames();this.recorded=[];this.recordedSamples=0;this.encoder=new PCM16Encoder(this.context.sampleRate);
      const ws=new WebSocket(this.url()+'&gap='+this.gapMs);this.socket=ws;
      const live=()=>this.socket===ws&&version===this.version&&activation===this.activation&&this.enabled;
      const timer=setTimeout(()=>{if(live())this.fail('流式识别连接超时');},14000);
      ws.onmessage=ev=>{if(!live())return;let d;try{d=JSON.parse(ev.data);}catch(_){this.fail('识别返回格式错误');return;}
        if(d.type==='ready'){clearTimeout(timer);this.suspended=false;this.onTurnStart();this.onState('listening');}
        if(d.type==='draft'){this.onDraft(d.text);}
        if(d.type==='speech_started'){clearTimeout(this.finalTimer);this.onState('speaking');}
        if(d.type==='speech_stopped'){clearTimeout(this.finalTimer);this.onState('finalizing');this.finalTimer=setTimeout(()=>this.fail('实时识别等待最终文字超时'),10000);}
        if(d.type==='done'){const text=d.text;this.suspend();if(text.trim())this.onUtterance(text);else this.resume();}
        if(d.type==='error')this.fail(d.error);
      };
      ws.onerror=()=>{clearTimeout(timer);if(live())this.fail('百炼实时识别连接失败');};
      ws.onclose=()=>{clearTimeout(timer);if(live())this.fail('实时识别连接中断，本段未提交');};
    }catch(e){if(version===this.version&&activation===this.activation)this.fail('麦克风未就绪：'+e.message);}
  }
  accept(frame,rate){
    if(this.suspended||!this.enabled||this.socket?.readyState!==1)return;
    this.recorded.push(new Float32Array(frame));this.recordedSamples+=frame.length;
    let sum=0;for(const v of frame)sum+=v*v;const rms=Math.sqrt(sum/frame.length);
    this.onActivity({level:Math.min(1,rms*12),quietMs:0,speaking:rms>.01});
    if(this.recordedSamples>rate*120){this.fail('单次发言超过两分钟，请分段交流');return;}
    if(this.socket.bufferedAmount>64000){this.fail('音频上传积压，已暂停收音');return;}
    this.socket.send(this.encoder.encode(frame));
  }
  fail(message){
    const rate=this.context?.sampleRate||16000,all=this.recorded||[];let frames=[],n=0;const recovery=[];
    const save=()=>{if(n>=rate*.2)recovery.push({index:recovery.length,revision:1,text:null,textRevision:0,failed:true,audio:wavBase64(frames,rate)});frames=[];n=0;};
    for(const f of all){frames.push(f);n+=f.length;if(n>=rate*24)save();}save();
    this.disable();this.recorded=[];this.onFailure(message,recovery);
  }
}
class PCMStreamPlayer {
  static context=null;
  static unlock(){
    if(!this.context||this.context.state==='closed')this.context=new (window.AudioContext||window.webkitAudioContext)({sampleRate:24000});
    return this.context.resume();
  }
  constructor(url,signal){
    this.chunks=[];this.bytes=0;this.sources=new Set();this.tail=null;this.done=false;this.stopped=false;
    this.ws=new WebSocket(url);this.ws.binaryType='arraybuffer';
    this.timer=setTimeout(()=>this.fail(new Error('流式合成等待超时')),35000);
    this.abort=()=>this.stop();this.signal=signal;signal?.addEventListener('abort',this.abort,{once:true});
    this.ws.onmessage=e=>{
      if(this.stopped)return;
      if(typeof e.data==='string'){
        let d;try{d=JSON.parse(e.data);}catch(_){this.fail(new Error('音频协议错误'));return;}
        if(d.type==='error')this.fail(new Error(d.error));
        if(d.type==='done'){this.done=true;clearTimeout(this.timer);if(this.tail!==null)this.fail(new Error('音频字节不完整'));else this.finish();}
      }else{
        this.bytes+=e.data.byteLength;if(this.bytes>2000000){this.fail(new Error('音频过长'));return;}
        this.chunks.push(e.data);if(this.playing)this.drain();
      }
    };
    this.ws.onerror=()=>this.fail(new Error('百炼流式合成连接失败'));
    this.ws.onclose=()=>{if(!this.done&&!this.stopped)this.fail(new Error('流式音频中断'));};
    if(signal?.aborted)this.stop();
  }
  async play(onFirst){
    if(this.error)throw this.error;if(this.stopped)return;
    await PCMStreamPlayer.unlock();if(this.stopped)return;
    this.context=PCMStreamPlayer.context;this.next=this.context.currentTime+.04;this.onFirst=onFirst;this.playing=true;
    return new Promise((resolve,reject)=>{this.resolve=resolve;this.reject=reject;this.drain();this.finish();});
  }
  drain(){
    for(const data of this.chunks.splice(0)){
      let bytes=new Uint8Array(data);
      if(this.tail!==null){const joined=new Uint8Array(bytes.length+1);joined[0]=this.tail;joined.set(bytes,1);bytes=joined;this.tail=null;}
      if(bytes.length%2){this.tail=bytes[bytes.length-1];bytes=bytes.subarray(0,bytes.length-1);}
      if(!bytes.length)continue;
      const buffer=this.context.createBuffer(1,bytes.length/2,24000),out=buffer.getChannelData(0),view=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);
      for(let i=0;i<out.length;i++)out[i]=view.getInt16(i*2,true)/32768;
      const src=this.context.createBufferSource();src.buffer=buffer;src.connect(this.context.destination);
      this.next=Math.max(this.next,this.context.currentTime+.025);
      if(!this.firstScheduled){this.firstScheduled=true;this.firstTimer=setTimeout(()=>{if(!this.stopped)this.onFirst?.();},Math.max(0,(this.next-this.context.currentTime)*1000));}
      this.sources.add(src);src.onended=()=>{src.disconnect();this.sources.delete(src);this.finish();};src.start(this.next);this.next+=buffer.duration;
    }
    if(this.done&&this.tail!==null)this.fail(new Error('音频字节不完整'));
  }
  finish(){if(this.playing&&this.done&&!this.chunks.length&&!this.sources.size&&!this.error){if(!this.bytes)this.fail(new Error('合成未返回声音'));else{this.cleanup();this.resolve?.();}}}
  cleanup(){clearTimeout(this.timer);clearTimeout(this.firstTimer);this.signal?.removeEventListener('abort',this.abort);this.ws.close();}
  fail(error){if(this.stopped||this.error)return;this.error=error;this.cleanup();for(const src of this.sources)src.stop();this.sources.clear();this.reject?.(error);}
  stop(){if(this.stopped)return;this.stopped=true;this.cleanup();for(const src of this.sources)src.stop();this.sources.clear();this.chunks=[];this.resolve?.();}
}
if(typeof module!=='undefined')module.exports={PCM16Encoder,PCMStreamPlayer,StreamingMicLoop};
