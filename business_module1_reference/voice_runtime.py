"""Continuous WebRTC conversation using real LiveKit Agents.

Existing Qwen/Whisper gateway calls are adapted to non-streaming STT/TTS.
Silero VAD supplies speech boundaries; the user never submits individual audio
clips. Batch gateway latency remains a measurable limitation.
"""
import asyncio
import base64
from datetime import timedelta
import io
import json
import os
import secrets
import socket
import sys
import threading
from urllib.parse import urlparse
import wave
from knowledge import ROOT

sys.path.insert(0,str(ROOT/'reference/coach/voice-demo'))


def voice_config(provider):
    url=os.environ.get('LIVEKIT_URL','')
    key=os.environ.get('LIVEKIT_API_KEY',''); secret=os.environ.get('LIVEKIT_API_SECRET','')
    if not all((url,key,secret)):
        return {'ready':False,'reason':'连续语音尚未配置LiveKit服务；当前可阅读资料和用文字练习。'}
    try:
        parsed=urlparse(url)
        with socket.create_connection((parsed.hostname,parsed.port or (443 if parsed.scheme=='wss' else 80)),timeout=.5):pass
    except OSError:
        return {'ready':False,'reason':'LiveKit语音服务未启动；当前可用文字练习。'}
    if not provider.readiness()['ready']:
        return {'ready':False,'reason':'请先连接对话与语音模型。'}
    return {'ready':True,'url':url,'transport':'livekit','speech_mode':'vad+batch-gateway'}


def token(room,identity):
    from livekit import api
    return api.AccessToken(os.environ['LIVEKIT_API_KEY'],os.environ['LIVEKIT_API_SECRET']).with_identity(identity).with_ttl(timedelta(minutes=5)).with_grants(api.VideoGrants(room_join=True,room=room,can_publish=True,can_subscribe=True)).to_jwt()


# Delayed imports keep reading courses independent of native audio libraries.
def gateway_types():
    from livekit import rtc
    from livekit.agents import stt,tts,DEFAULT_API_CONNECT_OPTIONS
    class GatewaySTT(stt.STT):
        def __init__(self):
            super().__init__(capabilities=stt.STTCapabilities(streaming=False,interim_results=False))
        async def _recognize_impl(self,buffer,*,language=None,conn_options=DEFAULT_API_CONNECT_OPTIONS):
            from asr_provider import transcribe
            frame=rtc.combine_audio_frames(buffer)
            if frame.sample_rate!=16000:
                resampler=rtc.AudioResampler(frame.sample_rate,16000,num_channels=frame.num_channels)
                frame=rtc.combine_audio_frames(resampler.push(frame)+resampler.flush())
            if frame.num_channels!=1:
                raise ValueError('语音输入需要单声道')
            output=io.BytesIO()
            with wave.open(output,'wb') as f:
                f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(bytes(frame.data))
            text=await asyncio.to_thread(transcribe,base64.b64encode(output.getvalue()).decode(),engine='auto')
            return stt.SpeechEvent(type=stt.SpeechEventType.FINAL_TRANSCRIPT,alternatives=[stt.SpeechData(language='zh',text=text)])
    class GatewayTTS(tts.TTS):
        def __init__(self):
            super().__init__(capabilities=tts.TTSCapabilities(streaming=False),sample_rate=24000,num_channels=1)
        def synthesize(self,text,*,conn_options=DEFAULT_API_CONNECT_OPTIONS):
            return GatewayStream(tts=self,input_text=text,conn_options=conn_options)
    class GatewayStream(tts.ChunkedStream):
        async def _run(self,emitter):
            from tts_provider import synthesize
            raw=await asyncio.to_thread(synthesize,self.input_text,'Andre')
            with wave.open(io.BytesIO(raw)) as w:
                if w.getnchannels()!=1 or w.getsampwidth()!=2:
                    raise ValueError('语音格式不兼容')
                data=w.readframes(w.getnframes());rate=w.getframerate()
            frame=rtc.AudioFrame(data,rate,1,len(data)//2)
            frames=[frame]
            if rate!=24000:
                resampler=rtc.AudioResampler(rate,24000,num_channels=1)
                frames=resampler.push(frame)+resampler.flush()
            emitter.initialize(request_id=secrets.token_hex(8),sample_rate=24000,num_channels=1,mime_type='audio/pcm')
            for frame in frames:emitter.push(bytes(frame.data))
            emitter.flush()
    return GatewaySTT,GatewayTTS


class VoiceService:
    def __init__(self,engine):
        self.engine=engine;self.loop=None;self.rooms={};self.guard=threading.Lock();self.last_error=None;self.tasks=set()
        if os.environ.get('LIVEKIT_URL'):
            # LiveKit registers plugins only on the main thread.
            from livekit.plugins import silero,openai

    def start(self,key,owner):
        from workflow import Problem
        config=voice_config(self.engine.provider)
        if not config['ready']:raise Problem(config['reason'],503)
        run=self.engine.load('runs',key,owner)
        if run['state']!='active':raise Problem('本次练习当前不能开始语音。',409)
        with self.guard:
            if self.loop is None:
                self.loop=asyncio.new_event_loop()
                threading.Thread(target=self.loop.run_forever,daemon=True).start()
        future=asyncio.run_coroutine_threadsafe(self._join(key,owner),self.loop)
        try:return future.result(timeout=30)
        except Exception as e:
            future.cancel()
            raise Problem('连续语音连接失败，尚未提交新的回答；请检查LiveKit服务。',503) from e

    def close(self):
        if self.loop and self.loop.is_running():
            async def shutdown():
                for record in list(self.rooms.values()):
                    try:await asyncio.wait_for(record['session'].aclose(),timeout=5)
                    except TimeoutError:pass
                    await record['room'].disconnect()
                for task in list(self.tasks):task.cancel()
                await asyncio.gather(*list(self.tasks),return_exceptions=True)
            asyncio.run_coroutine_threadsafe(shutdown(),self.loop).result(timeout=10)
            self.loop.call_soon_threadsafe(self.loop.stop)

    async def _join(self,key,owner):
        from livekit import rtc
        prior=self.rooms.pop(key,None)
        if prior:
            await prior['session'].aclose();await prior['room'].disconnect()
        # A new random room per connection prevents reuse of older join tokens.
        name='medrep-'+secrets.token_urlsafe(18)
        room=rtc.Room()
        await room.connect(os.environ['LIVEKIT_URL'],token(name,'doctor'))
        task=asyncio.create_task(self._session(key,owner,room))
        self.tasks.add(task);task.add_done_callback(self.tasks.discard)
        # _session initialization can fail before any client joins.
        await asyncio.sleep(.1)
        if task.done():task.result()
        return {'url':os.environ['LIVEKIT_URL'],'token':token(name,'rep'),'room':name}

    async def _session(self,key,owner,room):
        from livekit.agents import Agent,AgentSession,StopResponse
        from livekit.plugins import silero,openai
        engine=self.engine;service=self
        async def publish(kind,**data):
            await room.local_participant.publish_data(json.dumps({'type':kind,**data},ensure_ascii=False).encode(),reliable=True)
        class Doctor(Agent):
            def __init__(self):
                super().__init__(instructions='用普通话简短地与药代交流。医生发言由材料绑定的任务引擎提供。')
                self.next_text=''
            async def on_user_turn_completed(self,turn_ctx,new_message):
                text=new_message.text_content
                if not text.strip():raise StopResponse()
                try:
                    # LiveKit chat context tracks speech actually played, including
                    # truncation after interruption. Preserve that version in the run.
                    spoken=next((m.text_content for m in reversed(turn_ctx.items) if getattr(m,'role',None)=='assistant' and m.text_content),None)
                    if spoken:
                        with engine.lock(key):
                            raw=engine.load('runs',key,owner)
                            if raw['transcript'][-1]['role']=='医生':
                                raw['transcript'][-1]['text']=spoken
                                engine.save('runs',raw,owner)
                    run=engine.load('runs',key,owner)
                    result=await asyncio.to_thread(engine.answer,key,{'answer':text,'revision':run['revision'],'request_id':'voice-'+new_message.id},owner)
                    await publish('run_updated')
                    self.next_text=result['transcript'][-1]['text'] if result['state']=='active' else '这段练习结束了，可以查看刚才交流的反馈。'
                except Exception:
                    await publish('voice_error',message='语音回应处理失败；已转写的原话如已保存，可在页面重试。')
                    raise StopResponse()
            async def llm_node(self,chat_ctx,tools,model_settings):
                yield self.next_text
        try:
            STT,TTS=gateway_types()
            vad=silero.VAD.load(min_silence_duration=.8,max_buffered_speech=30)
            # The LLM node is overridden above; this object is not used to call a
            # separate provider. The task Engine owns all model calls and state.
            session=AgentSession(stt=STT(),tts=TTS(),vad=vad,llm=openai.LLM(api_key='unused-engine-owned'),
                                 turn_handling={'turn_detection':'vad','endpointing':{'min_delay':.5,'max_delay':2.5},
                                                'interruption':{'enabled':True,'mode':'vad','min_duration':.6},
                                                'preemptive_generation':{'enabled':False}})
            service.rooms[key]={'session':session,'room':room}
            disconnected=asyncio.Event()
            room.on('participant_disconnected',lambda _:disconnected.set())
            await asyncio.wait_for(session.start(agent=Doctor(),room=room),timeout=30)
            run=engine.load('runs',key,owner)
            await asyncio.wait_for(session.say(run['transcript'][-1]['text']),timeout=60)
            await asyncio.wait_for(disconnected.wait(),timeout=600)
        except Exception as exc:
            service.last_error=type(exc).__name__+': '+str(exc)[:200]
            try:await publish('voice_error',message='语音会话中断；可暂停语音后用文字继续。')
            except Exception:pass
        finally:
            record=service.rooms.get(key)
            if record and record['room'] is room:
                service.rooms.pop(key,None)
                await record['session'].aclose()
            await room.disconnect()
