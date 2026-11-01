"""Checks configured providers without displaying or persisting credentials."""
import asyncio,sys,os,json,base64
from pathlib import Path
from run_local import environment,ROOT
from pcm_test_audio import pcm_24k_to_16k
os.environ.update(environment());sys.path.insert(0,str(ROOT/'backend'))
import aiohttp
from platform_core.realtime_voice import open_remote,ASR,TTS,synthesize,event
async def main():
 results=[]
 async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=90),trust_env=False) as c:
  pcm=[]
  try:
   async def send(d):
    if d.get('type')=='audio':pcm.append(base64.b64decode(d['audio']))
   await synthesize(c,'这是本机模拟联调。今天练习清晰表达，先了解问题，再说明依据。',send,1,lambda:1)
   results.append({'provider':'tts','passed':True,'pcm_bytes':sum(map(len,pcm))})
  except Exception as e:results.append({'provider':'tts','passed':False,'error':str(e)[:250]})
  try:
   ws=await open_remote(c,ASR,{'input_audio_format':'pcm','sample_rate':16000,'input_audio_transcription':{'language':'zh'},'turn_detection':None})
   text=[]
   if pcm:
    data=pcm_24k_to_16k(b''.join(pcm))
    for i in range(0,len(data),3200):
     await ws.send_json(event('input_audio_buffer.append',audio=base64.b64encode(data[i:i+3200]).decode()))
    await ws.send_json(event('session.finish'))
    async with asyncio.timeout(30):
     async for m in ws:
      d=json.loads(m.data)
      if d.get('type')=='conversation.item.input_audio_transcription.completed':text.append(d.get('transcript',''))
      if d.get('type')=='error':raise ValueError(d.get('error',{}).get('code','ASR error'))
      if d.get('type')=='session.finished':break
   await ws.close();results.append({'provider':'asr','handshake':True,'synthetic_roundtrip':bool(text),'transcript':text})
  except Exception as e:results.append({'provider':'asr','handshake':False,'error':str(e)[:250]})
  try:
   async with c.post(os.environ['MEDREP_CHAT_API_URL'],headers={'Authorization':'Bearer '+os.environ['OPENAI_NEXT_API_KEY']},json={'model':os.environ['MEDREP_CHAT_MODEL'],'messages':[{'role':'user','content':'只回复：联调成功'}],'max_tokens':80,'thinking':{'type':'disabled'}}) as r:
    d=await r.json();results.append({'provider':'chat','model':os.environ['MEDREP_CHAT_MODEL'],'status':r.status,'reply':d.get('choices',[{}])[0].get('message',{}).get('content',''),'error_type':d.get('error',{}).get('type')})
  except Exception as e:results.append({'provider':'chat','error':type(e).__name__})
 print(json.dumps(results,ensure_ascii=False))
 (ROOT/'runtime/provider-check.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
asyncio.run(main())
