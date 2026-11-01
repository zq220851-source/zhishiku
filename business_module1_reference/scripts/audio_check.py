"""Synthetic speech loop, not a human microphone/accuracy acceptance."""
import json,urllib.request,urllib.error,http.cookiejar,io,wave,base64,time
from pathlib import Path
base='http://127.0.0.1:8791'
client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def req(path,body=None,binary=False):
 headers={'Content-Type':'application/json','Origin':base}
 request=urllib.request.Request(base+path,data=None if body is None else json.dumps(body).encode(),headers=headers)
 with client.open(request,timeout=75) as r:return r.read() if binary else json.load(r)
report={'type':'real_tts_asr_synthetic_loop','human_microphone_verified':False,'passed':False}
try:
 req('/api/config');r=req('/api/runs',{'mode':'learn','lesson_id':'demo-evidence'})
 start=time.time();raw=req('/api/audio/speak',{'run_id':r['id'],'message_index':0},True)
 with wave.open(io.BytesIO(raw)) as wav:report.update(audio_bytes=len(raw),duration_seconds=round(wav.getnframes()/wav.getframerate(),2))
 # Reuse the actual recorded stream constraints (mono, 16-bit, <=32s).
 with wave.open(io.BytesIO(raw)) as wav:
  frames=wav.readframes(wav.getnframes());rate=wav.getframerate();channels=wav.getnchannels();width=wav.getsampwidth()
 assert channels==1 and width==2
 trans=req('/api/audio/transcribe',{'run_id':r['id'],'audio':base64.b64encode(raw).decode()})
 report.update(transcript=trans['text'],submitted=trans['submitted'],seconds=round(time.time()-start,2))
 assert not trans['submitted']
 assert any(w in trans['text'] for w in ['材料','人群','指标'])
 report['passed']=True
except Exception as e:
 report['error_type']=type(e).__name__
Path('test-results/audio.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(('PASS' if report['passed'] else 'FAIL')+' synthetic TTS→ASR; human microphone not verified',flush=True)
raise SystemExit(0 if report['passed'] else 1)
