const $ = id => document.getElementById(id);
const state = {config:null,scenario:null,sessionId:null,transcript:[],corrections:{},busy:false,
  sound:true,finished:false,voiceId:null,audio:null,audioUrl:null,speechTicket:0,
  speechDone:null,epoch:0,deadline:0,timer:null,poll:null,ending:null,scoring:false,transcribing:false,transcriber:null,loop:null};
function escapeHtml(s){return String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));}
async function api(path,body,signal){const r=await fetch(path,{signal,method:body?"POST":"GET",headers:body?{"Content-Type":"application/json"}:{},body:body?JSON.stringify(body):undefined});const d=await r.json();if(!r.ok)throw new Error(d.error||`HTTP ${r.status}`);return d;}
function renderRubric(){const root=$("rubric-list");root.innerHTML="";state.config.scorecard.dimensions.forEach(d=>{const item=document.createElement("div");item.className="rubric-item";item.innerHTML=`<span class="rubric-number">${escapeHtml(d.id)}</span><div><b>${escapeHtml(d.name)}</b><small>${escapeHtml(d.domain)}</small></div>`;root.appendChild(item)});}
function displayMode(mode){const labels={credits:"生成式医生 · "+(state.config?.api_status?.model||"已连接"),minimax:"生成式医生 · MiniMax API",openai:"生成式医生 · OpenAI API",custom:"生成式医生 · 外部 API"};$("mode-pill").textContent=labels[mode]||mode;}
function applyApiStatus(){const cfg=state.config;$("api-connect").classList.toggle("hidden",cfg.provider_mode!=="credits");const ready=cfg.api_status.ready;$("start-btn").disabled=!ready;$("start-btn").innerHTML=ready?'开始模拟拜访 <span>↗</span>':"等待连接外部 API";if(ready){$("api-notice").classList.add("hidden");displayMode(cfg.provider_mode);}else{$("mode-pill").textContent="医生 API 未连接";$("api-notice").classList.remove("hidden");$("api-notice").textContent=cfg.provider_mode==="credits"?"请在上方填入 Credits 控制台生成的完整 API Key，验证通过后即可开始。":`需要先配置 ${cfg.api_status.missing.join("、")} 并重启服务器。`;}}
async function connectCredits(ev){ev.preventDefault();const input=$("api-key"),button=$("api-connect-btn"),message=$("api-connect-status");const key=input.value.trim();if(!key.startsWith("sk-")){message.textContent="请填写完整的 sk- 开头 API Key；活动 ID 或 UUID 无法调用接口。";message.classList.add("error");return;}button.disabled=true;button.textContent="正在验证…";message.textContent="正在向 Credits 验证模型连接";message.classList.remove("error");try{await api("/api/credentials",{api_key:key});input.value="";state.config=await api("/api/config");applyApiStatus();message.textContent="连接成功，可以开始模拟拜访。";}catch(e){message.textContent=e.message;message.classList.add("error");}finally{button.disabled=false;button.textContent="验证并连接";}}
function appendMessage(msg,index){const row=document.createElement("div");row.className="bubble-row "+(msg.role==="药代"?"rep":"doctor");const avatar=document.createElement("div");avatar.className="bubble-avatar";avatar.textContent=msg.role==="药代"?"你":"医";const content=document.createElement("div");content.className="bubble-content";const name=document.createElement("div");name.className="bubble-name";name.textContent=msg.role==="药代"?"你 · 医药代表":"模拟医生";const bubble=document.createElement("div");bubble.className="bubble";bubble.textContent=msg.text;const meta=document.createElement("div");meta.className="bubble-meta";meta.textContent=`发言 ${index+1}`;
 if(msg.role==="药代"){const edit=document.createElement("button");edit.textContent="修订转写";edit.onclick=()=>editMessage(index,bubble);meta.appendChild(edit)}
 content.append(name,bubble,meta);row.append(avatar,content);$("transcript").appendChild(row);$("transcript").scrollTop=$("transcript").scrollHeight;}
function editMessage(index,bubble){const previous=state.corrections[index]??state.transcript[index].text;const revised=window.prompt("修订这一轮药代发言。评分将使用修订稿：",previous);if(revised===null)return;if(!revised.trim()){error("发言不能留空");return;}state.corrections[index]=revised.trim();bubble.textContent=revised.trim();status("转写已修订，结束拜访后重算评分");}
function renderTranscript(){const box=$("transcript");box.innerHTML="";state.transcript.forEach((m,i)=>appendMessage(m,i));}
function initVoices(){const cfg=state.config.voice||{};state.voiceId=(cfg.choices||[]).some(v=>v.id==='Andre')?'Andre':cfg.default;for(const id of ["setup-voice-select","live-voice-select"]){const select=$(id);select.innerHTML="";for(const item of cfg.choices||[]){const option=document.createElement("option");option.value=item.id;option.textContent=item.label;select.appendChild(option)}select.value=state.voiceId;select.disabled=!cfg.available;select.onchange=()=>{state.voiceId=select.value;$(id==="setup-voice-select"?"live-voice-select":"setup-voice-select").value=state.voiceId;}}$("preview-voice-btn").disabled=!cfg.available;$("replay-btn").disabled=!cfg.available;if(!cfg.available)$("voice-setup-status").textContent="语音服务未安装；请按项目 README 安装 edge-tts。医生文字对话仍可使用。";}
function renderReport(r){
  $("radar-chart").innerHTML=radarMarkup(r.dimensions);
  $("radar-legend").innerHTML=r.dimensions.map(d=>`<li><a href="#score-${escapeHtml(d.id)}">${escapeHtml(d.name)}</a><b>${d.rating==="NA"?"NA":d.rating+" / 2"}</b></li>`).join("");
  $("report-context").innerHTML=`<p>${r.session?.end_reason==="timer"?"时间到，自动结束":r.session?.end_reason==="doctor"?"双方结束会面":"手动结束会面"} · 设定 ${r.session?.duration_seconds/60} 分钟</p>`+sourceLinks(r.scenario_sources||[]);

  $("report-summary").textContent=`${state.scenario.title} · ${r.coverage.rated}/${r.coverage.total} 个维度有可观察行为 · 无总分`;
  $("review-banner").textContent=`这是 ${r.scorecard_id} 的机器初评，尚待培训、医学及合规审核。${r.note}${r.hard_gate_review.length?` 另有 ${r.hard_gate_review.length} 条发言需人工合规复核。`:""}`;
  const root=$("score-results");root.innerHTML="";
  r.dimensions.forEach(d=>{
    const card=document.createElement("article");card.className="score-card";card.id="score-"+d.id;
    const sources=d.sources.slice(0,3).map(s=>s.url?`<a href="${escapeHtml(s.url)}" target="_blank" rel="noopener">${escapeHtml(s.id)} ↗</a>`:`<span title="${escapeHtml(s.locator)}">${escapeHtml(s.id)}</span>`).join(" · ");
    const allSources=d.sources.map(s=>`<li><b>${escapeHtml(s.id)}</b> ${escapeHtml(s.title)}${s.locator?`<br><small>${escapeHtml(s.locator)}</small>`:""}${s.url?` <a href="${escapeHtml(s.url)}" target="_blank" rel="noopener">打开原文 ↗</a>`:""}</li>`).join("");
    const quotes=d.transcript_spans.map(s=>`<div class="quote">“${escapeHtml(s.quote)}” <small>发言 ${s.turn_index+1}</small></div>`).join("");
    card.innerHTML=`<div class="score-top"><h3><small>${escapeHtml(d.id)}</small>${escapeHtml(d.name)}</h3><span class="rating ${d.rating==="NA"?"na":""}">${escapeHtml(d.rating)}</span></div><p class="score-reason">${escapeHtml(d.why)}</p>${quotes}<div class="source-line">依据：${sources}${d.sources.length>3?` 等 ${d.sources.length} 项`:""}</div><details class="anchor-details"><summary>查看 0 / 1 / 2 行为锚点</summary>${Object.entries(d.anchors).map(([n,t])=>`<p><b>${escapeHtml(n)}</b> ${escapeHtml(t)}</p>`).join("")}</details><details class="anchor-details"><summary>查看全部来源及定位</summary><ul>${allSources}</ul></details>`;
    root.appendChild(card);
  });
}
function status(text,busy=false){$('voice-status').textContent=text;$('voice-status').classList.toggle('busy',busy);}
function error(message){status(message,true);}
function setBusy(value){state.busy=value;updateControls();}
function updateControls(){
  $('retry-asr-btn').classList.toggle('hidden',!state.asrRecovery||state.finished);
  $('retry-asr-btn').disabled=state.busy||state.finished;
  $('send-btn').disabled=state.busy||state.finished;
  $('mic-btn').disabled=!state.loop||state.finished;
  $('score-btn').disabled=state.scoring;
  $('rep-input').disabled=state.finished;
  $('replay-btn').disabled=state.busy||state.finished||!state.config?.voice?.available;
  $('start-btn').disabled=state.busy||!state.config?.api_status.ready;
}
function sourceLinks(sources){return `<div class="scenario-sources">${sources.map(s=>`<a href="${escapeHtml(s.url)}" target="_blank" rel="noopener" title="${escapeHtml(s.locator)}">${escapeHtml(s.title)} ↗</a>`).join('')}</div>`;}
function setupScenarios(){
  const p=state.config.profile;
  $('profile-summary').innerHTML=`<strong>${escapeHtml(p.name)} · ${escapeHtml(p.bu)}</strong><span>日报虚构画像 · ${escapeHtml(p.role)}</span><p>负责：${p.marketed.map(x=>escapeHtml(x.name)).join('、')}<br>在研学习：${p.learning.map(x=>escapeHtml(x.name)).join('、')}（尚未获批）</p>`;
  const mine=$('scenario-filter').value==='mine';
  const scenes=state.config.scenarios.filter(s=>!['io_evidence','io_boundary'].includes(s.id)&&(mine?!!s.profile_id:!s.profile_id));
  $('scenario-list').innerHTML='';
  scenes.forEach(s=>{const btn=document.createElement('button');btn.className='scenario-card';btn.type='button';btn.dataset.id=s.id;
    btn.innerHTML=`<span class="scenario-icon">◇</span><span class="scenario-body"><strong>${escapeHtml(s.title)}</strong><small>${escapeHtml(s.tag)}</small><p>${escapeHtml(s.public.setting)}</p></span><span class="scenario-arrow">↗</span>`;
    btn.onclick=()=>chooseScenario(s.id);$('scenario-list').appendChild(btn);});
  if(scenes.length)chooseScenario(scenes[0].id);
}
function chooseScenario(id){
  state.scenario=state.config.scenarios.find(s=>s.id===id);
  document.querySelectorAll('.scenario-card').forEach(b=>b.classList.toggle('selected',b.dataset.id===id));
  const p=state.scenario.public;
  $('prep-card').innerHTML=`<h3>${escapeHtml(p.doctor)}</h3><p class="role">${escapeHtml(p.role)}</p>`+
    [['模拟地点',p.hospital],['负责产品',p.products],['会面环境',p.setting],['拜访关系',p.relationship],['已知关切',p.known_concern],['你的目标',p.visit_goal]].filter(x=>x[1]).map(([a,b])=>`<div class="prep-row"><b>${a}</b><span>${escapeHtml(b)}</span></div>`).join('')+
    sourceLinks(state.scenario.sources||[])+(state.scenario.design_note?`<p class="design-note">${escapeHtml(state.scenario.design_note)}</p>`:'');
}
function gapMs(){return Number($('turn-gap').value)||1200;}
function gapLabel(){return (gapMs()/1000)+' 秒';}
function realtimeMode(){return $('asr-engine').value==='realtime'&&state.config?.realtime?.ready;}
function realtimeUrl(kind,payload={}){return `ws://127.0.0.1:${state.config.realtime.port}/${kind}?`+new URLSearchParams(payload);}
function realtimeSettings(){
  const cfg=state.config.realtime,option=$('asr-engine').querySelector('[value="realtime"]');
  $('realtime-setup').classList.toggle('hidden',!cfg);
  option.disabled=!cfg?.ready;option.textContent=cfg?.ready?'百炼流式听写＋流式发声':'百炼流式听写＋流式发声 · 待配置';
  $('realtime-status').textContent=cfg?.ready?'已连接：默认使用百炼流式听写和流式发声。':'请先配置百炼，验证后即可使用流式听写和发声。';
}
async function connectRealtime(ev){
  ev.preventDefault();const button=$('realtime-connect-btn');button.disabled=true;$('realtime-status').textContent='正在分别验证识别与合成连接…';
  try{
    const config={api_key:$('realtime-key').value,workspace_id:$('realtime-workspace').value,region:$('realtime-region').value};
    $('realtime-key').value='';
    state.config.realtime=await api('/api/realtime/credentials',config,AbortSignal.timeout(32000));
    realtimeSettings();$('asr-engine').value='realtime';selectRecognition();
  }catch(e){$('realtime-status').textContent='连接未通过：'+e.message;}
  finally{button.disabled=false;}
}
function selectRecognition(){
  state.loop?.disable();state.transcriber?.cancel();state.asrRecovery=null;
  if(realtimeMode()&&!['Maia','Andre'].includes(state.voiceId)){state.voiceId='Andre';$('setup-voice-select').value='Andre';$('live-voice-select').value='Andre';}
  $('recognition-note').textContent=realtimeMode()?'正在说话时持续上传音频并显示草稿；停顿后只把最终转写交给 DeepSeek。医生首句生成后，百炼音频边收边播。失败录音可手动通过 Credits 重试；未完成文字不会用于评分。单次发言最多两分钟。医生说话时暂停收音，暂不支持打断。':'Credits 录音转写：说完后上传；主备模式最多等待 25 秒，失败后可重试录音。';
  for(const id of ['setup-voice-select','live-voice-select'])for(const option of $(id).options)option.disabled=realtimeMode()&&!['Maia','Andre'].includes(option.value);
  $('voice-setup-status').textContent=realtimeMode()?'百炼流式合成：使用 Maia / Andre，首批音频到达即可播放；请先试听直连效果。':'使用 Credits Qwen 音色或 Edge 备用音色。';
  initRecognition();updateControls();
}
function initRecognition(){
  if($('asr-engine').value==='realtime'&&!state.config?.realtime?.ready){state.loop=null;$('recognition-note').textContent='请先配置百炼流式语音。';return;}
  const Recognition=window.SpeechRecognition||window.webkitSpeechRecognition;
  const onState=mode=>{const on=mode==='listening'||mode==='speaking';$('mic-btn').classList.toggle('listening',on);$('mic-btn').setAttribute('aria-pressed',String(state.loop.enabled));$('mic-btn').setAttribute('aria-label',state.loop.enabled?'暂停连续语音':'开启连续语音');$('mic-caption').textContent=on?`正在听 · 停顿 ${gapLabel()}自动发送`:'连续语音已暂停';if(mode==='paused'){if(!state.finished&&!state.busy&&state.transcriber?.parts.length)$('rep-input').value=state.transcriber.draft().replaceAll('…','');state.transcriber?.cancel();$('capture-state').textContent='收音已暂停';$('capture-level').style.width='0%';}if(on){$('live-capture').classList.remove('hidden');$('capture-state').textContent='正在听';}if(on)status(mode==='speaking'?`正在听 · 停顿 ${gapLabel()}自动发送`:'正在听你说话');};
  if(state.config.recognition?.engine==='qwen_api'&&navigator.mediaDevices?.getUserMedia&&(window.AudioContext||window.webkitAudioContext)){
    state.transcriber=new LiveTranscriber({concurrency:1,finalPriority:false,
      transcribe:async(audio,signal,onPartial)=>{
        let d;try{d=await eventStream('/api/transcribe/stream',{session_id:state.sessionId,audio,engine:realtimeMode()?'auto':$('asr-engine').value},e=>{if(e.type==='draft')onPartial(e.text);if(e.type==='asr_status'&&!state.finished){const name=e.engine==='whisper'?'Whisper 主转写':'Qwen 备用转写';$('capture-hint').textContent=e.completed?name+'已完成':(e.fallback?(e.reason==='primary_slow'?'主转写较慢，备用已同时开始；采用先完成的结果。':'主转写暂不可用，正在使用 Qwen 备用转写。'):'正在使用 Whisper 主转写。');}},AbortSignal.any([signal,AbortSignal.timeout((realtimeMode()||$('asr-engine').value==='auto')?28000:45000)]));}catch(e){if(e.name==='TimeoutError')throw new Error('云端转写等待超时，本段未提交');throw e;}
        if(d.finished)throw new Error('会话已结束');return d.text;
      },
      onDraft:text=>{if(state.finished)return;showDraft(text);},
      onError:e=>{if(!state.finished)$('capture-hint').textContent='转写失败：'+e.message+'。本段尚未提交。';}
    });
    if(realtimeMode()){
      state.loop=new StreamingMicLoop({gapMs:gapMs(),url:()=>realtimeUrl('asr',{session_id:state.sessionId}),
        onTurnStart:()=>{state.asrRecovery=null;showDraft('正在实时听写…');updateControls();},
        onDraft:showDraft,
        onUtterance:text=>{if(state.finished||state.busy)return;showDraft(text);$('rep-input').value=text;send('voice_stream',text);},
        onActivity:({level,speaking})=>{if(speaking)state.lastSpeechAt=performance.now();$('capture-level').style.width=Math.round(level*100)+'%';},
        onState:mode=>{onState(mode);if(mode==='connecting'){$('capture-state').textContent='正在连接实时听写';status('正在连接实时听写',true);}if(mode==='finalizing'){$('capture-state').textContent='正在确认最后几个字';status('正在确认转写',true);}},
        onFailure:(message,recovery)=>{if(state.finished)return;state.asrRecovery=recovery.length?recovery:null;state.retryListen=true;updateControls();$('capture-hint').textContent=message+(recovery.length?'；录音已暂存，可点击重试，通过 Credits 备用识别。':'；请重试麦克风或输入文字。');error(message);},onError:error});return;
    }
    state.loop=new MicLoop({gapMs:gapMs(),segmentAtPause:false,endpointOnly:true,
      onTurnStart:()=>{state.asrRecovery=null;updateControls();state.transcriber.reset();showDraft('正在听，结束后显示转写…');$('capture-hint').textContent=`继续说即可；停顿 ${gapLabel()}后提交。说完后转写一次；长发言每 24 秒分段处理，不重复上传。`;},
      onChunk:(audio,meta)=>state.transcriber.push(audio,meta),onAudio:finishVoiceTurn,
      onActivity:({level,quietMs,speaking})=>{
        if(speaking&&quietMs===0)state.lastSpeechAt=performance.now();
        $('capture-level').style.width=Math.round(level*100)+'%';
        $('silence-progress').style.width=Math.min(100,quietMs/gapMs()*100)+'%';
        const text=speaking?(quietMs>=350?`停顿 ${(quietMs/1000).toFixed(1)} / ${gapLabel()}`:'听到你在说话'):'正在听 · 请开始说话';
        $('capture-state').textContent=text;
        if(speaking)$('mic-caption').textContent=quietMs>=350?'继续说话会重新计时':`正在听 · 停顿 ${gapLabel()}自动发送`;
      },onState,onError:error});return;
  }
  if(!Recognition){$('auto-listen').checked=false;$('auto-listen').disabled=true;$('mic-btn').disabled=true;
    $('recognition-note').textContent='当前浏览器未提供录音或语音识别，请使用新版 Chrome/Edge 打开本地地址。文字模式仍可用。';
    $('mic-caption').textContent='当前浏览器不支持语音识别';return;}
  $('recognition-note').textContent='当前使用浏览器语音识别服务，需允许麦克风。停顿 5 秒后自动发送，医生说完继续听。';
  state.loop=new SpeechLoop({Recognition,
    onDraft:text=>{if(state.finished)return;showDraft(text);},
    onUtterance:text=>send('voice',text),onState,onError:error
  });
}
function showDraft(text){
  $('live-capture').classList.remove('hidden');$('interim').classList.remove('hidden');
  $('interim').textContent=text;$('interim').scrollTop=$('interim').scrollHeight;
}
async function finishVoiceTurn(){
  if(state.finished||state.busy||!state.sessionId)return;
  const epoch=state.epoch;state.transcribing=true;setBusy(true);
  $('capture-state').textContent=`停顿已满 ${gapLabel()}`;
  $('capture-hint').textContent='正在转写本次发言，完成后医生自动接话。';
  status(`停顿已满 ${gapLabel()} · 正在确认转写`,true);
  try{
    const text=await state.transcriber.finish();
    if(epoch!==state.epoch||state.finished)return;
    state.transcribing=false;setBusy(false);
    if(text===null){status('转写已取消');return;}
    $('rep-input').value=text;
    if(text.trim()){
      showDraft(text);$('capture-state').textContent='已提交给医生';
      $('capture-hint').textContent='医生正在回复；说完后会自动继续听你讲话。';
      await send('voice_api',text);
    }else{showDraft('没有识别到清晰语音，请再说一次。');resumeListening();}
  }catch(e){if(epoch===state.epoch&&!state.finished){
    const draft=state.transcriber.draft();state.asrRecovery=state.transcriber.recovery();state.retryListen=state.loop?.enabled;const message=e.message;$('rep-input').value=draft.replaceAll('…','');
    state.loop?.disable();setBusy(false);$('capture-hint').textContent='转写失败：'+message+'。可重试本段录音，或重新开启麦克风。录音仅暂存在本页，刷新、开始新发言或结束会话会清除。';error(message+'；本段未提交，请点击重试或重新说话。');
  }}finally{if(epoch===state.epoch)state.transcribing=false;}
}
async function retryTranscription(){
  if(!state.asrRecovery||state.busy||state.finished)return;
  if(performance.now()>=state.deadline){endSession('timer');return;}
  const saved=state.asrRecovery;state.transcriber.restore(saved);state.asrRecovery=null;
  if(state.loop)state.loop.enabled=!!state.retryListen;
  await finishVoiceTurn();
}
function suspendListening(){state.transcriber?.cancel();state.loop?.suspend();$('mic-btn').classList.remove('listening');if(state.loop?.enabled)$('mic-caption').textContent='连续语音已开启 · 医生说完继续听';}
function resumeListening(){if(state.sessionId&&!state.finished&&!state.busy&&!state.audio&&!state.scoring){state.loop?.resume();if(!state.loop?.enabled)status('可以继续交流');}}
function stopSpeech(cancelQueue=true){
  state.pcmActive?.stop();state.pcmActive=null;
  if(cancelQueue){for(const p of state.pcmPool||[])p.stop();state.pcmPool?.clear();}
if(cancelQueue){state.audioEpoch=(state.audioEpoch||0)+1;for(const p of state.audioPool||[]){p.pause();p.removeAttribute('src');p.load();}state.audioPool?.clear();}state.audioController?.abort();state.speechTicket++;if(state.speechDone){state.speechDone();state.speechDone=null;}
  if(state.audio){state.audio.pause();state.audio.src='';state.audio=null;}if(state.audioUrl){URL.revokeObjectURL(state.audioUrl);state.audioUrl=null;}}
function prepareStreamingVoice(payload,signal){
  const voice=payload.voice||state.voiceId;
  if(realtimeMode()){
    const pcm=new PCMStreamPlayer(realtimeUrl('tts',{...payload,voice}),signal);
    (state.pcmPool??=new Set()).add(pcm);return {pcm};
  }
  // Qwen returns a complete, repaired WAV. Fetch it once and surface HTTP
  // failures directly instead of treating them as native-player format errors.
  if(['Maia','Andre'].includes(voice)){
    return fetch('/api/voice',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({...payload,voice}),signal:signal?AbortSignal.any([signal,AbortSignal.timeout(35000)]):AbortSignal.timeout(35000)
    }).then(async response=>{
      if(!response.ok){let message;try{message=(await response.json()).error;}catch(_){}throw new Error(message||`语音服务 HTTP ${response.status}`);}
      return {blob:await response.blob()};
    }).catch(error=>({error}));
  }
  const player=new Audio();player.preload='auto';
  player.src='/api/voice-stream?'+new URLSearchParams({...payload,voice:payload.voice||state.voiceId});
  (state.audioPool??=new Set()).add(player);player.load();return {player};
}
async function playVoice(payload,startedAt,preview=false,prepared=null){
  stopSpeech(false);suspendListening();const ticket=state.speechTicket;
  const show=(msg,busy=false)=>preview?$('voice-setup-status').textContent=msg:status(msg,busy);
  if(!state.config.voice?.available){show('普通话语音不可用，可阅读文字');return;}
  show(preview?'正在生成试听…':'医生正在接话…',true);
  const controller=new AbortController();state.audioController=controller;const timeout=setTimeout(()=>controller.abort(),35000);
  try{
    const ready=prepared?await prepared:(state.config.voice_revision>=3?await prepareStreamingVoice(payload,controller.signal):null);if(ready?.error)throw ready.error;
    if(ticket!==state.speechTicket)return;
    if(ready?.pcm){
      state.pcmActive=ready.pcm;
      await ready.pcm.play(()=>{show(preview?'正在试听流式音色':'医生正在说话 · 流式播放');if(startedAt)$('latency').textContent=`从停止说话到音频开始播放 ${((performance.now()-startedAt)/1000).toFixed(1)} 秒`;});
      state.pcmPool?.delete(ready.pcm);if(state.pcmActive===ready.pcm)state.pcmActive=null;
      if(ticket===state.speechTicket)show(preview?'试听结束':'可以继续交流');return;
    }
    let player=ready?.player,blob=ready?.blob,played=false;
    const play=player=>new Promise((resolve,reject)=>{
      state.audio=player;state.speechDone=resolve;
      player.onended=()=>resolve();player.onerror=()=>reject(new Error('流式语音播放中断'));
      player.onplaying=()=>{if(ticket===state.speechTicket&&!played){played=true;clearTimeout(timeout);show(preview?'正在试听普通话音色':'医生正在说话');if(startedAt)$('latency').textContent=`从${state.lastSpeechAt?"停止说话":"发送"}到开始播放 ${((performance.now()-startedAt)/1000).toFixed(1)} 秒${ready?.player&&!['Maia','Andre'].includes(payload.voice||state.voiceId)&&player.networkState===2?' · 边接收边播':''}`;}};
      controller.signal.addEventListener('abort',()=>{player.pause();player.removeAttribute('src');player.load();reject(new DOMException('播放已取消','AbortError'));},{once:true});
      if(controller.signal.aborted)return reject(new DOMException('播放已取消','AbortError'));
      if(player.error)return reject(new Error('流式音频不可用'));
      player.play().catch(reject);
    });
    if(player){
      try{await play(player);if(ticket===state.speechTicket)show(preview?'试听结束':'可以继续交流');return;}
      catch(e){if(played||controller.signal.aborted||ticket!==state.speechTicket||e.name==='NotAllowedError')throw e;
        player.pause();player.removeAttribute('src');player.load();state.audioPool.delete(player);
        show('流式播放不可用，改用整句播放',true);}
    }
    if(!blob){const response=await fetch('/api/voice',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...payload,voice:state.voiceId}),signal:controller.signal});
    if(!response.ok){const d=await response.json();throw new Error(d.error||`HTTP ${response.status}`);}blob=await response.blob();}if(ticket!==state.speechTicket)return;
    state.audioUrl=URL.createObjectURL(blob);player=new Audio(state.audioUrl);state.audio=player;
    await play(player);
    if(ticket===state.speechTicket)show(preview?'试听结束':'可以继续交流');
  }catch(e){if(ticket===state.speechTicket)show('语音不可用：'+(e.name==='AbortError'?'合成超时':e.message));}
  finally{clearTimeout(timeout);if(ticket===state.speechTicket){state.speechDone=null;if(state.audioUrl)URL.revokeObjectURL(state.audioUrl);state.audioPool?.delete(state.audio);state.audio=null;state.audioUrl=null;state.audioController=null;}}
}
async function speak(index,startedAt){if(state.sound&&!state.finished)await playVoice({session_id:state.sessionId,message_index:index},startedAt);}
function clearTimers(){clearInterval(state.timer);clearInterval(state.poll);state.timer=null;state.poll=null;}
function syncTiming(d){state.deadline=performance.now()+d.remaining_seconds*1000;tick();}
function tick(){
  const left=Math.max(0,Math.ceil((state.deadline-performance.now())/1000));
  $('timer').textContent=`${String(Math.floor(left/60)).padStart(2,'0')}:${String(left%60).padStart(2,'0')}`;
  $('timer').classList.toggle('urgent',left<=30);
  if(left===0&&state.sessionId&&!state.finished)endSession('timer');
}
function beginTimers(d){
  clearTimers();syncTiming(d);state.timer=setInterval(tick,250);
  const epoch=state.epoch;let polling=false;
  state.poll=setInterval(async()=>{if(polling||state.finished)return;polling=true;try{
    const snap=await api('/api/session/'+state.sessionId);
    if(epoch!==state.epoch||state.finished)return;
    if(snap.finished){state.transcript=snap.transcript;renderTranscript();endSession(snap.end_reason,snap);}else syncTiming(snap);
  }catch(_){}finally{polling=false;}},3000);
}
function durationSeconds(){const value=$('duration-select').value;const n=value==='custom'?Number($('custom-duration').value)*60:Number(value);if(!Number.isInteger(n)||n<30||n>3600)throw new Error('请输入 0.5–60 分钟的时长。');return n;}
async function start(){
  if($('asr-engine').value==='realtime'&&!state.config?.realtime?.ready){$('api-notice').textContent='请先配置百炼流式语音。';$('api-notice').classList.remove('hidden');return;}
  if(state.busy)return;if(state.loop){state.loop.gapMs=gapMs();state.loop.segmentAtPause=false;}let duration;try{duration=durationSeconds();}catch(e){$('api-notice').textContent=e.message;$('api-notice').classList.remove('hidden');return;}
  if(realtimeMode()){try{await PCMStreamPlayer.unlock();}catch(e){error('请点击开启声音后重试');return;}}
  const epoch=++state.epoch;$('api-notice').classList.add('hidden');setBusy(true);stopSpeech();$('start-btn').textContent='正在准备会面…';
  try{
    if($('auto-listen').checked&&state.loop?.prepare)await state.loop.prepare();
    const d=await api('/api/session',{scenario_id:state.scenario.id,duration_seconds:duration});if(epoch!==state.epoch)return;
    state.sessionId=d.session_id;state.transcript=d.transcript;state.corrections={};state.finished=false;state.ending=null;
    displayMode(d.mode);const p=d.card;$('doctor-name').textContent=p.doctor;$('doctor-role').textContent=p.role;$('visit-title').textContent=state.scenario.title;
    $('visit-details').innerHTML=[['模拟地点',p.hospital],['负责产品',p.products],['会面环境',p.setting],['已知关切',p.known_concern],['拜访目标',p.visit_goal]].filter(x=>x[1]).map(([a,b])=>`<dt>${a}</dt><dd>${escapeHtml(b)}</dd>`).join('');
    $('setup').classList.add('hidden');$('report').classList.add('hidden');$('live').classList.remove('hidden');$('end-notice').classList.add('hidden');
    renderTranscript();$('rep-input').value='';$('live-capture').classList.remove('hidden');$('interim').textContent='你说的话会显示在这里。';$('capture-state').textContent='收音未开启';$('silence-progress').style.width='0%';$('capture-level').style.width='0%';
    if(state.loop)state.loop.enabled=$('auto-listen').checked;
    beginTimers(d);window.scrollTo({top:0,behavior:'smooth'});
    await speak(0);
  }catch(e){state.loop?.disable();$('api-notice').classList.remove('hidden');$('api-notice').textContent=e.message;error(e.message);}
  finally{if(epoch===state.epoch){setBusy(false);$('start-btn').innerHTML='开始模拟拜访 <span>↗</span>';resumeListening();}}
}
async function send(inputMethod='text',voiceText){
  const text=(voiceText??$('rep-input').value).trim();
  if(inputMethod==='text')state.lastSpeechAt=null;
  if(!text||state.busy||!state.sessionId||state.finished)return;
  if(performance.now()>=state.deadline){endSession('timer');return;}
  if(text.length>1200){state.loop?.disable();error('这段发言过长，请缩短到 1200 字内再发送。');return;}
  state.asrRecovery=null;const epoch=state.epoch;let failed=false;stopSpeech();suspendListening();setBusy(true);status('医生正在回应',true);const started=performance.now();
  try{
    let playback=Promise.resolve(),first=true;const audioEpoch=state.audioEpoch;
    state.turnController=new AbortController();
    const d=await eventStream('/api/turn/stream',{session_id:state.sessionId,text,input_method:inputMethod},event=>{
      if(epoch!==state.epoch||state.finished)return;
      if(event.type==='accepted')$('rep-input').value='';
      if(event.type==='sentence'){
        state.transcript=event.transcript;renderTranscript();
        const firstSentence=first;first=false;
        if(firstSentence)$('latency').textContent=`首句文字 ${(event.elapsed_ms/1000).toFixed(1)} 秒`;
        if(state.sound&&audioEpoch===state.audioEpoch){
          const payload={session_id:state.sessionId,speech_id:event.speech_id,voice:state.voiceId};
          const prepared=state.config.voice_revision>=3?prepareStreamingVoice(payload,state.turnController.signal):fetch('/api/voice',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:AbortSignal.any([state.turnController.signal,AbortSignal.timeout(35000)])}).then(async r=>{if(!r.ok)throw new Error((await r.json()).error||'语音合成失败');return {blob:await r.blob()};}).catch(error=>({error}));
          playback=playback.then(()=>{if(!failed&&audioEpoch===state.audioEpoch&&epoch===state.epoch&&!state.finished&&state.sound)return playVoice(payload,firstSentence?(inputMethod.startsWith('voice')?state.lastSpeechAt||started:started):null,false,prepared);});
        }
      }
    },state.turnController.signal);
    await playback;
    if(epoch!==state.epoch||state.finished)return;
    state.transcript=d.transcript;renderTranscript();$('rep-input').value='';
    if(d.doctor){displayMode(d.doctor.mode);if(!state.sound)$('latency').textContent=`文字回应 ${d.generation_ms} ms`;}
    if(d.finished){endSession(d.end_reason,d);return;}
    syncTiming(d);
  }catch(e){if(epoch!==state.epoch||state.finished)return;
    failed=true;state.turnController?.abort();stopSpeech();
    // The server keeps the submitted rep utterance if the model failed.
    try{const snap=await api('/api/session/'+state.sessionId);if(epoch===state.epoch&&!state.finished){state.transcript=snap.transcript;renderTranscript();if(snap.transcript.at(-1)?.text===text)$('rep-input').value='';}}catch(_){}
    failed=true;state.loop?.disable();error(e.message);
  }finally{if(epoch===state.epoch&&!state.finished){setBusy(false);if(!failed)resumeListening();}}
}
function endSession(reason='user',snapshot){
  if(state.ending)return state.ending;
  if(!state.sessionId)return Promise.resolve();
  const epoch=state.epoch;state.turnController?.abort();state.finished=true;state.asrRecovery=null;state.loop?.disable();stopSpeech();clearTimers();setBusy(false);
  const draft=$('rep-input').value.trim(),pendingAudio=state.transcribing;
  const notice=reason==='timer'?'时间到，拜访已自动结束。':reason==='doctor'?'本次会面已结束。':'拜访已结束。';
  $('end-notice').textContent=notice+(draft?' 未发送的草稿保留在输入框，未计入评分。':'')+(pendingAudio?' 到点时仍在转写的语音尚无可核实文字，未计入本次初评。':'');$('end-notice').classList.remove('hidden');
  if(reason==='timer')$('timer').textContent='00:00';
  state.ending=(async()=>{try{
    const d=snapshot||await api('/api/end',{session_id:state.sessionId});if(epoch!==state.epoch)return;
    state.transcript=d.transcript;renderTranscript();await score();
  }catch(e){if(epoch===state.epoch)error(e.message+'；可点击查看评分重试。');}})();
  return state.ending;
}
async function score(){
  if(!state.sessionId||state.scoring)return;
  if(!state.finished)return endSession('user');
  const epoch=state.epoch;state.scoring=true;updateControls();status('正在生成六维评分',true);$('score-btn').textContent='正在评分…';
  try{const d=await api('/api/score',{session_id:state.sessionId,corrections:state.corrections});if(epoch!==state.epoch)return;
    state.transcript=d.transcript;renderReport(d);$('live').classList.add('hidden');$('report').classList.remove('hidden');window.scrollTo({top:0,behavior:'smooth'});
  }catch(e){if(epoch===state.epoch)error('评分未完成：'+e.message+'；可点击重试评分。');}
  finally{if(epoch===state.epoch){state.scoring=false;updateControls();$('score-btn').textContent='重新生成评分';}}
}
function reset(){
  const sid=state.sessionId;state.turnController?.abort();++state.epoch;state.loop?.disable();stopSpeech();clearTimers();
  if(sid&&!state.finished)api('/api/end',{session_id:sid}).catch(()=>{});
  Object.assign(state,{asrRecovery:null,sessionId:null,transcript:[],corrections:{},finished:false,busy:false,ending:null,scoring:false,transcribing:false});
  $('report').classList.add('hidden');$('live').classList.add('hidden');$('setup').classList.remove('hidden');$('score-btn').textContent='结束拜访 · 查看评分';updateControls();applyApiStatus();window.scrollTo({top:0,behavior:'smooth'});
}
async function init(){try{
  state.config=await api('/api/config');if(state.config.voice_revision<8&&['8765','8766','8767','8768','8769','8770','8771','8772','8773'].includes(location.port)){location.replace('http://127.0.0.1:8774/');return;}if(!state.config.voice_revision&&['8765','8766','8767'].includes(location.port)){location.replace('http://127.0.0.1:8768/');return;}if(!state.config.recognition&&location.hostname==='127.0.0.1'&&['8765','8766'].includes(location.port)){location.replace('http://127.0.0.1:8767/');return;}setupScenarios();renderRubric();applyApiStatus();initVoices();realtimeSettings();$('asr-engine').value=state.config?.realtime?.ready?'realtime':'auto';$('turn-gap').value='1200';selectRecognition();
  $('retry-asr-btn').onclick=retryTranscription;
  $('api-connect').addEventListener('submit',connectCredits);$('scenario-filter').onchange=setupScenarios;
  $('asr-engine').onchange=selectRecognition;
  $('realtime-connect').addEventListener('submit',connectRealtime);
  $('realtime-disconnect-btn').onclick=async()=>{try{state.config.realtime=await api('/api/realtime/disconnect',{});$('asr-engine').value='realtime';realtimeSettings();selectRecognition();}catch(e){$('realtime-status').textContent=e.message;}};
  $('turn-gap').onchange=()=>{if(state.loop)state.loop.gapMs=gapMs();};
  $('duration-select').onchange=()=>$('custom-duration-label').classList.toggle('hidden',$('duration-select').value!=='custom');
  $('preview-voice-btn').onclick=async()=>{if($('asr-engine').value==='realtime'&&!state.config?.realtime?.ready){$('voice-setup-status').textContent='请先配置百炼流式语音。';return;}if(realtimeMode())await PCMStreamPlayer.unlock();return playVoice({preview:true},null,true);};
  $('replay-btn').onclick=async()=>{if(state.sessionId&&!state.finished){const idx=state.transcript.findLastIndex(m=>m.role==='医生');await speak(idx);resumeListening();}};
  $('start-btn').onclick=start;$('send-btn').onclick=()=>send('text');$('score-btn').onclick=()=>state.finished?score():endSession('user');
  $('mic-btn').onclick=()=>{if(!state.loop||state.finished)return;if(state.loop.enabled)state.loop.disable();else{state.loop.enabled=true;if(!state.busy&&!state.audio)state.loop.resume();$('mic-btn').setAttribute('aria-pressed','true');}};
  $('back-btn').onclick=()=>{$('report').classList.add('hidden');$('live').classList.remove('hidden');status('会话已结束 · 可修订转写并重新评分');};
  $('new-btn').onclick=reset;$('restart-btn').onclick=reset;
  $('sound-btn').onclick=()=>{state.sound=!state.sound;$('sound-btn').classList.toggle('muted',!state.sound);$('sound-btn').title=state.sound?'静音医生语音':'开启医生语音';$('sound-btn').setAttribute('aria-label',$('sound-btn').title);if(!state.sound){stopSpeech();resumeListening();}};
  $('rep-input').addEventListener('keydown',ev=>{if(ev.key==='Enter'&&(ev.metaKey||ev.ctrlKey)){ev.preventDefault();send('text');}});
  document.addEventListener('visibilitychange',()=>{if(!document.hidden&&state.sessionId&&!state.finished)tick();});
  window.addEventListener('pagehide',()=>{state.loop?.disable();stopSpeech();});
}catch(e){document.body.innerHTML=`<div style="padding:40px">加载失败：${escapeHtml(e.message)}。请重新启动本地服务器。</div>`;}}
init();
