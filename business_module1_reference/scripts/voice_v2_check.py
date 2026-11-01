"""Real local WebRTC + VAD + gateway STT/TTS, synthetic fictional user audio.

Conversation semantics use an explicit model double; this verifies transport and
speech adaptation independently of real-model task generation.
"""
import argparse,asyncio,json,os,sys,tempfile,time,io,wave
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.credentials import configure
parser=argparse.ArgumentParser();parser.add_argument('--config-from',required=True);parser.add_argument('--real-model',action='store_true');args=parser.parse_args();configure(args.config_from)
settings=Path('runtime/livekit-local.json')
if settings.exists():
 c=json.loads(settings.read_text());os.environ.update(LIVEKIT_URL=c['url'],LIVEKIT_API_KEY=c['key'],LIVEKIT_API_SECRET=c['secret'])
else:os.environ.update(LIVEKIT_URL='ws://127.0.0.1:7880',LIVEKIT_API_KEY='devkey',LIVEKIT_API_SECRET='secret')
from app import RemoteDoctorProvider
from workflow import Engine
from voice_runtime import VoiceService
from tests.doubles import ScriptedProvider,FIXTURES as F
from tts_provider import synthesize
from livekit import rtc
out=Path('test-results/v2');out.mkdir(parents=True,exist_ok=True)

async def main():
 with tempfile.TemporaryDirectory() as td:
  engine=Engine(Path(td)/'voice.db',RemoteDoctorProvider() if args.real_model else ScriptedProvider());owner='synthetic-audio-test'
  r=engine.create({'mode':'learn','lesson_id':'demo-evidence'},owner)
  voice=VoiceService(engine)
  info=await asyncio.to_thread(voice.start,r['id'],owner)
  room=rtc.Room();received=[];data=[]
  @room.on('track_subscribed')
  def subscribed(track,publication,participant):
   async def consume():
    async for event in rtc.AudioStream(track):received.append(event.frame.samples_per_channel)
   asyncio.create_task(consume())
  @room.on('data_received')
  def message(packet):data.append(json.loads(packet.data))
  await room.connect(info['url'],info['token'])
  source=rtc.AudioSource(24000,1);track=rtc.LocalAudioTrack.create_audio_track('synthetic-mic',source)
  await room.local_participant.publish_track(track,rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE))
  raw=await asyncio.to_thread(synthesize,F['learning']['good'],'Andre')
  (out/'fictional-user.wav').write_bytes(raw)
  # Wait for the doctor's first audio to prove automatic playback, then a quiet
  # period so the synthetic answer doesn't test accidental initial overlap.
  deadline=time.monotonic()+65
  while not received and time.monotonic()<deadline:await asyncio.sleep(.1)
  assert received,'Doctor audio was not published automatically: '+str(voice.last_error)
  await asyncio.sleep(12)
  with wave.open(io.BytesIO(raw)) as f:pcm=f.readframes(f.getnframes());rate=f.getframerate()
  frame=rtc.AudioFrame(pcm,rate,1,len(pcm)//2)
  if rate!=24000:
   rs=rtc.AudioResampler(rate,24000,num_channels=1);frame=rtc.combine_audio_frames(rs.push(frame)+rs.flush())
  pcm=bytes(frame.data)
  # Feed actual PCM over WebRTC; no /answer or /transcribe HTTP submission.
  for start in range(0,len(pcm),960):
   chunk=pcm[start:start+960]
   if len(chunk)<960:chunk+=b'\0'*(960-len(chunk))
   await source.capture_frame(rtc.AudioFrame(chunk,24000,1,480))
  for _ in range(100):await source.capture_frame(rtc.AudioFrame(b'\0'*960,24000,1,480))
  deadline=time.monotonic()+85
  while time.monotonic()<deadline:
   r=engine.load('runs',r['id'],owner)
   if any(m['role']=='药代' for m in r['transcript']) and r['state'] in ('active','review') and not r.get('pending_request'):break
   if any(m.get('type')=='voice_error' for m in data):raise RuntimeError(str(data))
   await asyncio.sleep(.2)
  assert any(m['role']=='药代' for m in r['transcript']) and r['state'] in ('active','review'),'Audio turn did not complete: '+str(voice.last_error)
  if args.real_model:assert r['state']=='review','Expected the authored bounded response to complete this fictional task'
  result={'passed':True,'transport':'real LiveKit WebRTC','speech':'real Credits gateway, synthetic input','conversation_model':engine.provider.readiness()['model'],'doctor_audio_samples':sum(received),'transcript':r['transcript'],'state':r['state'],'events':data,'limitation':'Not a real-human microphone/turn-taking acceptance test.'}
  (out/'voice.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in result.items() if k not in ('transcript','events')},ensure_ascii=False))
  await asyncio.to_thread(voice.close)
  await room.disconnect()

asyncio.run(main())
