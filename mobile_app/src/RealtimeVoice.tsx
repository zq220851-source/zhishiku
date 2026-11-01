import {useEffect,useRef,useState} from 'react';
import {apiBase,voiceAccessToken,request} from './api';
import type {CoachRun} from './api';

type Props={kind:'coach'|'review';recordId:string;onRun?:(run:CoachRun)=>void;onTranscript?:(text:string)=>void;onActive?:(active:boolean)=>void;disabled?:boolean;enabled?:boolean};
type AudioResources={socket?:WebSocket;context?:AudioContext;stream?:MediaStream;node?:AudioWorkletNode;source?:MediaStreamAudioSourceNode;analyser?:AnalyserNode;playing:Set<AudioBufferSourceNode>;next:number;generation:number;frame?:number;timer?:number;pausing?:boolean;flush?:()=>void;playbackStart?:number;audioDone?:boolean};
const fresh=():AudioResources=>({playing:new Set(),next:0,generation:0});
function companion(detail:{state?:string;level?:number}){window.dispatchEvent(new CustomEvent('medrep:voice',{detail}));}
export default function RealtimeVoice(props:Props){
 const latest=useRef(props);latest.current=props;
 const resources=useRef<AudioResources>(fresh()),attempt=useRef(0),mounted=useRef(true);
 const [active,setActive]=useState(false),[busy,setBusy]=useState(false),[status,setStatus]=useState('麦克风未开启'),[draft,setDraft]=useState(''),[error,setError]=useState('');
 function playback(completed:boolean){const r=resources.current;if(r.playbackStart!==undefined&&r.socket?.readyState===WebSocket.OPEN){r.socket.send(JSON.stringify({type:'playback',generation:r.generation,completed,played_ms:Math.round(Math.max(0,(r.context?.currentTime||0)-r.playbackStart)*1000)}));r.playbackStart=undefined;}}
 function silence(){const r=resources.current;playback(false);for(const source of r.playing){source.onended=null;try{source.stop();}catch{/* already ended */}source.disconnect();}r.playing.clear();r.next=0;companion({level:0});}
 function dispose(){attempt.current++;const r=resources.current;silence();clearTimeout(r.timer);cancelAnimationFrame(r.frame||0);r.node?.disconnect();r.source?.disconnect();r.analyser?.disconnect();r.stream?.getTracks().forEach(t=>t.stop());r.socket?.close();if(r.context&&r.context.state!=='closed')void r.context.close();resources.current=fresh();companion({state:'awake',level:0});latest.current.onActive?.(false);window.dispatchEvent(new CustomEvent('medrep:recording',{detail:false}));if(mounted.current){setActive(false);setBusy(false);setDraft('');}}
 function pause(){const r=resources.current;if(r.pausing)return;if(r.socket?.readyState!==WebSocket.OPEN){dispose();return;}r.pausing=true;setBusy(true);setStatus('正在保存最后一段语音…');silence();const n=attempt.current;
  const finish=()=>{r.source?.disconnect();r.stream?.getTracks().forEach(t=>t.stop());if(r.socket?.readyState===WebSocket.OPEN)r.socket.send(JSON.stringify({type:'stop'}));};
  if(r.node){r.flush=finish;r.node.port.postMessage('flush');}else finish();
  r.timer=window.setTimeout(()=>{if(n===attempt.current){setError('最后一段语音尚未确认，请查看记录后重连');dispose();}},125000);
 }
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;dispose();};},[props.recordId]);
 useEffect(()=>{if(props.enabled===false){if(resources.current.socket?.readyState===WebSocket.OPEN)pause();else dispose();}},[props.enabled]);
 useEffect(()=>{const hide=()=>{if(document.hidden&&resources.current.socket)pause();};document.addEventListener('visibilitychange',hide);return()=>document.removeEventListener('visibilitychange',hide);},[]);
 async function start(){if(busy||active||props.enabled===false)return;setBusy(true);setError('');setStatus('正在检查语音配置…');const generation=++attempt.current;
  try{
   await request('/v1/mobile/voice/config');if(generation!==attempt.current)return;
   if(!navigator.mediaDevices?.getUserMedia)throw Error('当前环境无法使用麦克风，请使用 HTTPS 或本机浏览器');
   setStatus('正在请求麦克风…');
   const context=new AudioContext({sampleRate:16000});resources.current.context=context;await context.resume();
   const stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
   if(generation!==attempt.current){stream.getTracks().forEach(t=>t.stop());return;}resources.current.stream=stream;
   await context.audioWorklet.addModule('/voice-pcm.js');if(generation!==attempt.current)return;
   const source=context.createMediaStreamSource(stream),node=new AudioWorkletNode(context,'voice-pcm');resources.current.source=source;resources.current.node=node;
   const analyser=context.createAnalyser();analyser.fftSize=1024;analyser.connect(context.destination);resources.current.analyser=analyser;
   const samples=new Float32Array(analyser.fftSize);const level=()=>{if(generation!==attempt.current)return;analyser.getFloatTimeDomainData(samples);let sum=0;for(const f of samples)sum+=f*f;companion({level:Math.min(1,Math.max(0,(Math.sqrt(sum/samples.length)-.01)*9))});resources.current.frame=requestAnimationFrame(level);};level();
   const url=new URL(apiBase());url.protocol=url.protocol==='https:'?'wss:':'ws:';url.pathname='/v1/mobile/voice/'+props.kind+'/'+encodeURIComponent(props.recordId);
   const socket=new WebSocket(url);resources.current.socket=socket;let ready=false;
   node.port.onmessage=e=>{if(generation!==attempt.current)return;if(e.data?.type==='flushed'){resources.current.flush?.();resources.current.flush=undefined;return;}if(ready&&socket.readyState===WebSocket.OPEN){if(socket.bufferedAmount>512000){setError('网络上传过慢，最后一段可能尚未保存，请检查记录');dispose();return;}socket.send(e.data);}};
   resources.current.timer=window.setTimeout(()=>{if(!ready&&generation===attempt.current){setError('语音连接超时，请检查服务配置');dispose();}},25000);
   socket.onopen=()=>{if(generation!==attempt.current)return;setStatus('正在连接实时语音服务…');socket.send(JSON.stringify({type:'auth',token:voiceAccessToken()}));};
   socket.onmessage=e=>{if(generation!==attempt.current)return;try{const m=JSON.parse(e.data);const r=resources.current;
    if(m.type==='ready'){clearTimeout(r.timer);ready=true;source.connect(node);node.connect(context.destination);setActive(true);setBusy(false);latest.current.onActive?.(true);window.dispatchEvent(new CustomEvent('medrep:recording',{detail:true}));setStatus('已连接，请自然说话');companion({state:'listening'});}
    if(m.type==='draft')setDraft(m.text);
    if(m.type==='transcript'){setDraft('');latest.current.onTranscript?.(m.text);}
    if(m.type==='thinking'){setDraft('');setStatus('医生正在思考…');companion({state:'thinking'});}
    if(m.type==='speaking'){silence();r.generation=m.generation;r.audioDone=false;setStatus('医生正在说话，可以开口打断');companion({state:'speaking'});}
    if(m.type==='interrupt'){silence();r.generation=m.generation;setStatus('正在听你说…');companion({state:'listening'});}
    if(m.type==='listening'){r.audioDone=true;if(!r.playing.size){playback(true);setStatus('请自然回应医生');companion({state:'listening'});}}
    if(m.type==='run'){latest.current.onRun?.(m.run);setDraft('');}
    if(m.type==='audio'&&m.generation===r.generation&&!r.pausing){const bytes=Uint8Array.from(atob(m.audio),c=>c.charCodeAt(0));if(bytes.length%2)throw Error('语音数据格式错误');const pcm=new DataView(bytes.buffer),buffer=context.createBuffer(1,bytes.length/2,m.sample_rate);const floats=buffer.getChannelData(0);for(let i=0;i<floats.length;i++)floats[i]=pcm.getInt16(i*2,true)/32768;const audio=context.createBufferSource();audio.buffer=buffer;audio.connect(analyser);r.playing.add(audio);audio.onended=()=>{r.playing.delete(audio);audio.disconnect();if(!r.playing.size&&r.audioDone){playback(true);if(mounted.current)setStatus('请自然回应医生');companion({state:'listening'});}};r.next=Math.max(context.currentTime+.03,r.next);r.playbackStart??=r.next;audio.start(r.next);r.next+=buffer.duration;}
    if(m.type==='paused'){dispose();setStatus('已暂停，最后一段已处理');}
    if(m.type==='complete'){dispose();setStatus('本轮训练已结束');}
    if(m.type==='error'){setError(m.message);dispose();setStatus('语音未完成，请检查后重连');}
   }catch{setError('语音响应无法读取，请检查记录后重连');dispose();}};
   socket.onerror=()=>{if(generation===attempt.current){setError('实时语音连接失败，请检查服务器和网络');dispose();}};
   socket.onclose=()=>{if(generation===attempt.current){setError('连接已断开，最后一段可能尚未保存，请检查记录');dispose();setStatus('语音已断开');}};
  }catch(e){if(generation===attempt.current){setError(e instanceof Error?e.message:'无法开启语音');dispose();setStatus('未连接');}}
 }
 return <div className={'realtime-voice '+(active?'is-live':'')}><div className="voice-orb" aria-hidden="true">◉</div><p role="status">{status}</p><p className="minor">{props.kind==='coach'?'连续语音对话 · 自动识别停顿 · 支持打断':'连续口述 · 停顿自动转写 · 结束后核对原文'}</p>{draft&&<p className="voice-draft">{draft}</p>}{error&&<p className="error" role="alert">{error}</p>}<button className={active?'outline':'primary'} disabled={props.disabled||busy||props.enabled===false} onClick={()=>{if(active)pause();else void start();}}>{busy?status:active?'暂停语音':'连接麦克风，开始实时语音'}</button></div>;
}
