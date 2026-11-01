"""Verify deadlines and concurrent replies without consuming external API calls."""
import sys
import threading
import time
import unittest
import json
import http.client
import urllib.request
import urllib.error
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server
from doctor_engine import DoctorState, SCENARIOS

class FakeProvider:
    provider = 'test'
    def readiness(self): return {'ready': True}
    def chat(self, *args, **kwargs): return '可以，您接着说。'

class SessionsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        cls.base = f'http://127.0.0.1:{cls.http.server_port}'
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True); cls.thread.start()
    @classmethod
    def tearDownClass(cls): cls.http.shutdown(); cls.http.server_close()
    def setUp(self):
        self.p1=patch('server.RemoteDoctorProvider', FakeProvider);self.p1.start()
        self.p2=patch('doctor_engine.RemoteDoctorProvider', FakeProvider);self.p2.start()
    def tearDown(self):
        self.p1.stop();self.p2.stop()
        with server.LOCK:
            for s in server.SESSIONS.values(): s['timer'].cancel()
            server.SESSIONS.clear()
    def call(self, path, body=None):
        req=urllib.request.Request(self.base+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=5) as r: return r.status,json.load(r)
        except urllib.error.HTTPError as r: return r.code,json.load(r)
    def new(self,duration=300):
        status,d=self.call('/api/session',{'scenario_id':'io_first','duration_seconds':duration});self.assertEqual(status,200);return d
    def test_stream_delivers_first_sentence_before_generation_finishes(self):
        d=self.new();sid=d['session_id'];release=threading.Event()
        def streaming(text,history,remaining,on_sentence=None):
            on_sentence('可以，您说。');release.wait(2)
            on_sentence('资料可以稍后发来。');return '可以，您说。资料可以稍后发来。','test',None
        request=urllib.request.Request(self.base+'/api/turn/stream',data=json.dumps({'session_id':sid,'text':'您好'}).encode(),headers={'Content-Type':'application/json','Origin':self.base})
        with patch.object(DoctorState,'respond',side_effect=streaming):
            with urllib.request.urlopen(request,timeout=4) as response:
                events=[]
                for line in response:
                    if not line.startswith(b'data:'):continue
                    event=json.loads(line[5:]);events.append(event)
                    if event['type']=='sentence' and not release.is_set():
                        self.assertTrue(server.SESSIONS[sid]['pending'])
                        self.assertEqual(event['text'],'可以，您说。');release.set()
                self.assertEqual(events[-1]['type'],'done')
                self.assertEqual(events[-1]['transcript'][-1]['text'],'可以，您说。资料可以稍后发来。')
        self.assertFalse(server.SESSIONS[sid]['pending'])
    def test_stream_rejects_late_sentence_after_deadline(self):
        d=self.new();sid=d['session_id']
        def streaming(text,history,remaining,on_sentence=None):
            server.expire_session(sid);on_sentence('不应出现的回复')
        request=urllib.request.Request(self.base+'/api/turn/stream',data=json.dumps({'session_id':sid,'text':'您好'}).encode(),headers={'Content-Type':'application/json','Origin':self.base})
        with patch.object(DoctorState,'respond',side_effect=streaming):
            with urllib.request.urlopen(request,timeout=4) as response:
                events=[json.loads(line[5:]) for line in response if line.startswith(b'data:')]
        self.assertEqual(events[-1]['type'],'error')
        self.assertNotIn('sentence',[e['type'] for e in events])
        self.assertEqual(len(server.SESSIONS[sid]['transcript']),2)
    def test_presets_custom_and_invalid(self):
        for duration in [300,600,30,90,3600]:
            d=self.new(duration);self.assertAlmostEqual(d['remaining_seconds'],duration,delta=1)
        for duration in [0,29,3601,True,'300',30.5]:
            self.assertEqual(self.call('/api/session',{'scenario_id':'io_first','duration_seconds':duration})[0],400)
    def test_audio_stream_arrives_before_synthesis_finishes(self):
        release=threading.Event()
        def synthetic(text,voice,on_audio=None):
            on_audio(b'a'*2048);release.wait(2);on_audio(b'b'*2048)
        request=urllib.request.Request(self.base+'/api/voice-stream?preview=true',headers={'Origin':self.base})
        with patch('server.synthesize',side_effect=synthetic):
            with urllib.request.urlopen(request,timeout=4) as response:
                self.assertEqual(response.headers['Transfer-Encoding'],'chunked')
                self.assertEqual(response.read(2048),b'a'*2048)
                release.set();self.assertEqual(response.read(),b'b'*2048)
    def test_audio_stream_rejects_foreign_origin(self):
        request=urllib.request.Request(self.base+'/api/voice-stream?preview=true',headers={'Origin':'https://example.com'})
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request,timeout=3)
        self.assertEqual(caught.exception.code,403)
    def test_audio_stream_failure_is_not_a_successful_partial_download(self):
        def broken(text,voice,on_audio=None):
            on_audio(b'a'*2048)
            raise server.SpeechError('test interruption')
        request=urllib.request.Request(self.base+'/api/voice-stream?preview=true',headers={'Origin':self.base})
        with patch('server.synthesize',side_effect=broken):
            with urllib.request.urlopen(request,timeout=4) as response:
                with self.assertRaises(http.client.IncompleteRead):response.read()
    def test_timer_fires_without_browser(self):
        d=self.new(30);sid=d['session_id']
        with server.LOCK:
            s=server.SESSIONS[sid];s['timer'].cancel();s['deadline_mono']=time.monotonic()+0.04
            s['timer']=threading.Timer(.04,server.expire_session,args=(sid,));s['timer'].start()
        time.sleep(.07)
        self.assertTrue(server.SESSIONS[sid]['ended'])
        status,result=self.call('/api/turn',{'session_id':sid,'text':'迟到的发言'})
        self.assertTrue(result['finished']);self.assertEqual(len(result['transcript']),1)
        self.assertEqual(result['end_reason'],'timer')
    def test_deadline_during_model_call_discards_late_answer(self):
        d=self.new();sid=d['session_id'];entered=threading.Event();release=threading.Event();output=[]
        def slow(*args): entered.set();release.wait(3);return '超时的医生回复','test',None
        with patch.object(DoctorState,'respond',side_effect=slow):
            thread=threading.Thread(target=lambda:output.append(self.call('/api/turn',{'session_id':sid,'text':'我先说明资料边界。'})));thread.start()
            self.assertTrue(entered.wait(2));server.expire_session(sid)
            snap=self.call('/api/session/'+sid)[1]
            self.assertTrue(snap['finished']);self.assertEqual(len(snap['transcript']),2)
            release.set();thread.join(3)
        self.assertEqual(len(output[0][1]['transcript']),2)
        self.assertEqual(output[0][1]['end_reason'],'timer')
    def test_end_and_score_freeze_session(self):
        sid=self.new()['session_id']
        self.call('/api/end',{'session_id':sid});self.call('/api/end',{'session_id':sid})
        status,report=self.call('/api/score',{'session_id':sid})
        self.assertEqual(status,200);self.assertEqual(report['coverage']['rated'],0)
        self.assertEqual(len(report['dimensions']),6)
        self.assertTrue(self.call('/api/turn',{'session_id':sid,'text':'再说一句'})[1]['finished'])
    def test_no_forced_eight_turn_end(self):
        d=DoctorState(SCENARIOS['io_first'])
        for _ in range(12):d.respond('谢谢您的解释，我继续说明。',[],300)
        self.assertFalse(d.finished)
        d.respond('今天就到这里，再见。',[],10);self.assertTrue(d.finished)
    def test_asr_rejects_invalid_audio_before_api(self):
        from asr_provider import transcribe
        for audio in ['invalid base64', '', 'AAAA', 'A'*6_000_001]:
            with self.assertRaises(ValueError): transcribe(audio)
    def test_asr_is_rejected_after_expiry(self):
        sid=self.new()['session_id'];server.expire_session(sid)
        req=urllib.request.Request(self.base+'/api/transcribe',data=json.dumps({'session_id':sid,'audio':'invalid'}).encode(),headers={'Content-Type':'application/json','Origin':self.base})
        with patch('server.transcribe') as mock:
            with urllib.request.urlopen(req) as r:self.assertTrue(json.load(r)['finished'])
            mock.assert_not_called()
    def test_source_profile_matching(self):
        for sid in ['io_first','io_evidence','io_boundary']:
            s=SCENARIOS[sid]
            self.assertEqual(s['product_ids'],server.PROFILE['productIds'])
            self.assertTrue(s['sources']);self.assertIn('尚未',server.PROFILE['learning'][0]['status'])

if __name__=='__main__':unittest.main()
