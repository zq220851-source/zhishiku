"""Synthetic PCM integration test; no microphone recording or real visit data."""
import asyncio,os,sys,json,base64
from run_local import ROOT,environment
from pcm_test_audio import pcm_24k_to_16k
os.environ.update(environment());sys.path.insert(0,str(ROOT/'backend'))
import aiohttp
from platform_core.realtime_voice import synthesize
async def main():
 results={'test_kind':'SYNTHETIC_PCM_NOT_MICROPHONE','events':[]};audio=[]
 async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=180),trust_env=False) as c:
  async def collect(d):
   if d.get('type')=='audio':audio.append(base64.b64decode(d['audio']))
  await synthesize(c,'这是模拟练习。我会先确认医生关注的问题，再根据课程资料说明两条路线的区别。没有确认的信息，我会回去核实资料以后再回复。',collect,1,lambda:1)
  pcm=pcm_24k_to_16k(b''.join(audio))
  async with c.post('http://localhost:9011/v1/mobile/auth/login',json=json.loads((ROOT/'runtime/local-account.json').read_text())) as r:token=(await r.json())['access_token']
  run=json.loads((ROOT/'runtime/live-run.json').read_text());rid=run['id']
  async with c.ws_connect('http://localhost:9011/v1/mobile/voice/coach/'+rid,headers={'Origin':'http://localhost:5190'}) as ws:
   await ws.send_json({'type':'auth','token':token});started=False;sender=None;stop=False;received=0
   async def upload():
    for i in range(0,len(pcm),3200):
     await ws.send_bytes(pcm[i:i+3200]);await asyncio.sleep(.1)
    for _ in range(18):await ws.send_bytes(bytes(3200));await asyncio.sleep(.1)
   async with asyncio.timeout(140):
    async for m in ws:
     if m.type!=aiohttp.WSMsgType.TEXT:break
     d=json.loads(m.data);typ=d.get('type')
     if typ=='audio':received+=len(base64.b64decode(d['audio']))
     elif typ!='draft':results['events'].append(typ)
     if typ=='listening' and not started:started=True;sender=asyncio.create_task(upload())
     elif typ=='listening' and stop:
      await ws.send_json({'type':'stop'})
     elif typ=='run':results['saved_run_id']=d['run']['id'];results['turns']=len(d['run']['transcript']);stop=True
     elif typ=='error':results['error']=d.get('message');break
     elif typ=='paused':break
   if sender:await sender
   results['received_tts_bytes']=received
  async with c.get('http://localhost:9011/v1/mobile/coach/runs/'+rid,headers={'Authorization':'Bearer '+token}) as r:
   saved=await r.json();results['persisted_turns']=len(saved.get('transcript',[]));results['recognized_reply']=next((m['text'] for m in saved.get('transcript',[]) if m['role']=='药代'),None)
 results['passed']=bool(results.get('recognized_reply')) and 'paused' in results['events'] and not results.get('error') and results['received_tts_bytes']>0
 (ROOT/'runtime/voice-flow-check.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print(json.dumps(results,ensure_ascii=False))
asyncio.run(main())
