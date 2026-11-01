'use strict';
// Continuous audio is enabled only when the actual room/worker is available.
window.MedRepVoice = (()=>{
 let room=null,run=null,connecting=false,active=false,ready=false,generation=0;
 const status=t=>{document.getElementById('voice-status').textContent=t;};
 async function stop(){++generation;active=false;const r=room;room=null;if(r)await r.disconnect();document.getElementById('voice-stop').hidden=true;document.getElementById('voice-start').hidden=false;document.querySelectorAll('[data-voice-audio]').forEach(e=>e.remove());}
 async function bind(r){
   run=r;
   try{const c=await api('/api/voice/config');ready=c.ready;document.getElementById('voice-start').disabled=!c.ready||r.state!=='active';status(c.ready?'连续语音可用，首次使用需允许麦克风':c.reason);}
   catch(_){ready=false;document.getElementById('voice-start').disabled=true;status('连续语音服务尚未启动；可用文字练习。');}
 }
 async function start(){
   if(connecting||room||!run)return;connecting=true;const attempt=++generation;
   try{
     const c=await api('/api/runs/'+run.id+'/voice',{});
     if(attempt!==generation)return;
     if(!window.LivekitClient)throw new Error('语音客户端未加载');
     room=new LivekitClient.Room({adaptiveStream:true});
     room.on(LivekitClient.RoomEvent.TrackSubscribed,(track)=>{if(track.kind==='audio'){const element=track.attach();element.dataset.voiceAudio='true';document.body.appendChild(element);}});
     room.on(LivekitClient.RoomEvent.TrackUnsubscribed,track=>track.detach().forEach(e=>e.remove()));
     room.on(LivekitClient.RoomEvent.DataReceived,async data=>{
       try{const message=JSON.parse(new TextDecoder().decode(data));if(message.type==='run_updated'){
          const latest=await api('/api/runs/'+run.id);run=latest;state.run=latest;
          // Preserve the active room; openRun would disconnect it.
          $('transcript').innerHTML=latest.transcript.map(m=>`<div class="bubble ${m.role==='药代'?'rep':''}"><strong>${esc(m.role)}</strong>${esc(m.text)}</div>`).join('');
          if(latest.state==='review'){await stop();openRun(latest);}else status('正在听，请自然回应');
       }else if(message.type==='voice_error'){await stop();const latest=await api('/api/runs/'+run.id);openRun(latest);error(new Error(message.message));}}
       catch(e){error(e);}
     });
     await room.connect(c.url,c.token);if(attempt!==generation){await stop();return;}await room.startAudio();await room.localParticipant.setMicrophoneEnabled(true,{echoCancellation:true,noiseSuppression:true,autoGainControl:true});
     active=true;$('voice-stop').hidden=false;$('voice-start').hidden=true;status('已连接，医生即将开口');
   }catch(e){await stop();status('语音连接失败；回答不会自动补写。');error(e);}finally{connecting=false;}
 }
 document.addEventListener('DOMContentLoaded',()=>{$('voice-start').onclick=start;$('voice-stop').onclick=stop;});
 return {bind,stop,isActive:()=>active,isReady:()=>ready};
})();
