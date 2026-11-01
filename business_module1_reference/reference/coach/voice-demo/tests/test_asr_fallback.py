import io,sys,unittest,urllib.error
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import asr_provider as a
from remote_provider import RemoteAPIError

def failure(code):
 e=RemoteAPIError('测试接口错误');e.__cause__=urllib.error.HTTPError('https://example.test',code,'failure',{},io.BytesIO());return e
class FallbackTests(unittest.TestCase):
 def setUp(self):a._whisper_retry_at=0
 def tearDown(self):a._whisper_retry_at=0
 def test_success_never_calls_backup(self):
  with patch.object(a,'transcribe',return_value='原话') as t:
   self.assertEqual(a.transcribe_resilient('audio'),'原话');self.assertEqual(t.call_count,1);self.assertEqual(t.call_args.kwargs['engine'],'whisper')
 def test_429_falls_back_once_and_next_call_skips_cooling_primary(self):
  events=[]
  with patch.object(a,'transcribe',side_effect=[failure(429),'备用原话','下次原话']) as t:
   self.assertEqual(a.transcribe_resilient('audio',on_status=events.append),'备用原话');self.assertEqual(a.transcribe_resilient('next'),'下次原话')
   self.assertEqual([c.kwargs['engine'] for c in t.call_args_list],['whisper','qwen','qwen']);self.assertTrue(events[-1]['completed'])
 def test_auth_bad_audio_and_empty_speech_do_not_trigger_backup(self):
  for error in [failure(401),failure(403),failure(400),ValueError('bad audio')]:
   with self.subTest(error=str(error)),patch.object(a,'transcribe',side_effect=error) as t:
    with self.assertRaises(Exception):a.transcribe_resilient('audio')
    self.assertEqual(t.call_count,1)
  with patch.object(a,'transcribe',return_value='') as t:
   self.assertEqual(a.transcribe_resilient('audio'),'');self.assertEqual(t.call_count,1)
 def test_timeout_uses_backup_and_double_failure_does_not_return_text(self):
  for primary in [RemoteAPIError('连接超时'),failure(503)]:
   with patch.object(a,'transcribe',side_effect=[primary,failure(503)]) as t:
    with self.assertRaisesRegex(RemoteAPIError,'转写未完成'):a.transcribe_resilient('audio')
    self.assertEqual(t.call_count,2)
 def test_session_end_at_status_prevents_backup(self):
  def notify(info):
   if info['fallback']:raise RemoteAPIError('会话已结束')
  with patch.object(a,'transcribe',side_effect=failure(503)) as t:
   with self.assertRaisesRegex(RemoteAPIError,'会话已结束'):a.transcribe_resilient('audio',on_status=notify)
   self.assertEqual(t.call_count,1)

class DeadlineTests(unittest.TestCase):
 def test_total_deadline_cancels_slow_body_not_just_connection(self):
  import threading,time
  from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
  class Slow(BaseHTTPRequestHandler):
   def log_message(self,*args):pass
   def do_POST(self):
    self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers()
    try:
     for _ in range(100):self.wfile.write(b' ');self.wfile.flush();time.sleep(.02)
    except (BrokenPipeError,ConnectionResetError):pass
  server=ThreadingHTTPServer(('127.0.0.1',0),Slow);threading.Thread(target=server.serve_forever,daemon=True).start()
  try:
   req=__import__('urllib.request',fromlist=['Request']).Request('http://127.0.0.1:'+str(server.server_port),data=b'{}')
   start=time.monotonic()
   with self.assertRaises(TimeoutError):a.request_bytes(req,.12)
   self.assertLess(time.monotonic()-start,.7)
  finally:server.shutdown();server.server_close()
 def test_slow_primary_stays_alive_and_backup_can_win(self):
  import time,threading
  calls=[];cancel_seen=threading.Event()
  def attempt(*args,**kw):
   calls.append(kw['engine'])
   if kw['engine']=='qwen':return '备用完成'
   while not a._request_context.cancelled.wait(.01):pass
   cancel_seen.set();raise RemoteAPIError('连接已取消')
  a._whisper_retry_at=0
  with patch.object(a,'HEDGE_DELAY',.03),patch.object(a,'transcribe',side_effect=attempt):
   self.assertEqual(a.transcribe_resilient('audio'),'备用完成')
   self.assertTrue(cancel_seen.wait(.3))
  self.assertEqual(calls,['whisper','qwen'])
 def test_total_budget_stops_both_requests(self):
  def attempt(*args,**kw):
   a._request_context.cancelled.wait(1)
   raise RemoteAPIError('连接已取消')
  a._whisper_retry_at=0
  with patch.object(a,'HEDGE_DELAY',.02),patch.object(a,'TOTAL_TIMEOUT',.1),patch.object(a,'transcribe',side_effect=attempt):
   with self.assertRaisesRegex(RemoteAPIError,'总等待上限'):a.transcribe_resilient('audio')
 def test_backup_error_does_not_abort_still_running_primary(self):
  import time
  def attempt(*args,**kw):
   if kw['engine']=='qwen':raise RemoteAPIError('连接异常')
   time.sleep(.12);return '主接口完整结果'
  a._whisper_retry_at=0
  with patch.object(a,'HEDGE_DELAY',.02),patch.object(a,'transcribe',side_effect=attempt):
   self.assertEqual(a.transcribe_resilient('audio'),'主接口完整结果')
 def test_network_operation_releases_connection_when_cancelled(self):
  import threading,time
  from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
  class Slow(BaseHTTPRequestHandler):
   def log_message(self,*args):pass
   def do_POST(self):
    self.send_response(200);self.end_headers()
    try:
     for _ in range(100):self.wfile.write(b' ');self.wfile.flush();time.sleep(.02)
    except (BrokenPipeError,ConnectionResetError):pass
  server=ThreadingHTTPServer(('127.0.0.1',0),Slow);threading.Thread(target=server.serve_forever,daemon=True).start()
  cancel=threading.Event();a._request_context.cancelled=cancel
  timer=threading.Timer(.1,cancel.set);timer.start()
  try:
   req=__import__('urllib.request',fromlist=['Request']).Request('http://127.0.0.1:'+str(server.server_port),data=b'{}')
   begin=time.monotonic()
   with self.assertRaisesRegex(RemoteAPIError,'已取消'):a.request_bytes(req,10)
   self.assertLess(time.monotonic()-begin,.7)
  finally:
   timer.cancel();del a._request_context.cancelled;server.shutdown();server.server_close()
