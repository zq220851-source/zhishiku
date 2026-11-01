import asyncio,json,sys,unittest,base64
from pathlib import Path
from unittest.mock import patch,AsyncMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import realtime_voice as r
import aiohttp
from aiohttp.test_utils import TestServer,TestClient

class ConfigTests(unittest.TestCase):
 def test_unsafe_workspace_and_unknown_region_rejected(self):
  for data in [{'workspace_id':'x.evil.test/path','region':'beijing'},{'workspace_id':'x','region':'other'}]:
   with self.assertRaises(ValueError):r.parse_config({'api_key':'sk-placeholder-test',**data})
 def test_config_not_saved_on_failed_verification(self):
  with patch.object(r,'_config',None),patch.object(r,'verify_config',new=AsyncMock(side_effect=ValueError('bad'))):
   with self.assertRaises(ValueError):r.configure({'api_key':'sk-placeholder-test','workspace_id':'space','region':'beijing'})
   self.assertFalse(r.public_config()['configured']);self.assertNotIn('key',r.public_config())
 def test_protocol_fixed_formats_and_safe_host(self):
  c=r.parse_config({'api_key':'sk-placeholder-test','workspace_id':'space','region':'beijing'})
  self.assertEqual(r.endpoint(c,r.ASR_MODEL),'wss://space.cn-beijing.maas.aliyuncs.com/api-ws/v1/realtime?model=qwen3-asr-flash-realtime')
  self.assertEqual(r.asr_settings()['session']['sample_rate'],16000)
  self.assertEqual(r.tts_settings()['session']['response_format'],'pcm')
  with self.assertRaises(ValueError):r.tts_settings('unregistered')

class Msg:
 def __init__(self,data):self.type=aiohttp.WSMsgType.TEXT;self.data=json.dumps(data)
class FakeRemote:
 def __init__(self):self.queue=asyncio.Queue();self.sent=[];self.closed=False
 async def send_json(self,d):
  self.sent.append(d)
  if d['type']=='input_audio_buffer.append':
   await self.queue.put(Msg({'type':'conversation.item.input_audio_transcription.text','text':'医','stash':'生'}))
   await self.queue.put(Msg({'type':'conversation.item.input_audio_transcription.completed','transcript':'医生您好'}))
  if d['type']=='input_text_buffer.commit':
   await self.queue.put(Msg({'type':'response.audio.delta','delta':base64.b64encode(b'\x01\x00'*100).decode()}))
 def __aiter__(self):return self
 async def __anext__(self):return await self.queue.get()
 async def close(self):self.closed=True

class BridgeTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.remote=FakeRemote();self.active=True
  self.config=patch.object(r,'snapshot',return_value={'key':'not-real','workspace':'test','region':'beijing'});self.config.start()
  self.connect=patch.object(r,'connect',new=AsyncMock(return_value=self.remote));self.connect.start()
  self.server=TestServer(r.make_app('http://127.0.0.1:8775',lambda sid:self.active and sid=='valid',lambda args:'医生测试'))
  self.client=TestClient(self.server);await self.client.start_server();r._bridge_port=self.server.port
 async def asyncTearDown(self):
  await self.client.close();self.connect.stop();self.config.stop()
 async def test_origin_and_expired_session_blocked_before_upstream(self):
  for origin,sid,status in [('https://evil.test','valid',403),('http://127.0.0.1:8775','expired',400)]:
   with self.assertRaises(aiohttp.WSServerHandshakeError) as e:await self.client.ws_connect('/asr?session_id='+sid,headers={'Origin':origin})
   self.assertEqual(e.exception.status,status)
  r.connect.assert_not_awaited()
 async def test_binary_audio_stream_draft_then_complete(self):
  ws=await self.client.ws_connect('/asr?session_id=valid',headers={'Origin':'http://127.0.0.1:8775'})
  self.assertEqual((await ws.receive_json())['type'],'ready')
  await ws.send_bytes(b'\0\0'*1600)
  self.assertEqual(await ws.receive_json(),{'type':'draft','text':'医生'})
  self.assertEqual(await ws.receive_json(),{'type':'done','text':'医生您好'})
  await ws.close()
 async def test_tts_delivers_pcm_before_completion_and_cancels_on_end(self):
  ws=await self.client.ws_connect('/tts?session_id=valid&voice=Maia',headers={'Origin':'http://127.0.0.1:8775'})
  self.assertEqual((await ws.receive_json())['type'],'ready')
  audio=await ws.receive();self.assertEqual(audio.type,aiohttp.WSMsgType.BINARY);self.assertEqual(len(audio.data),200)
  self.active=False
  result=await ws.receive_json();self.assertEqual(result['type'],'error');self.assertIn('会话已结束',result['error'])
  await ws.close()
 async def test_tts_done_requires_audio_and_completed_status(self):
  ws=await self.client.ws_connect('/tts?session_id=valid&voice=Maia',headers={'Origin':'http://127.0.0.1:8775'})
  await ws.receive_json();await ws.receive()
  await self.remote.queue.put(Msg({'type':'response.done','response':{'status':'failed'}}))
  self.assertEqual((await ws.receive_json())['type'],'error');await ws.close()

class EntitlementTests(unittest.IsolatedAsyncioTestCase):
 async def test_top_level_unpurchased_does_not_turn_into_generic_disconnect(self):
  from unittest.mock import Mock
  remote=FakeRemote()
  await remote.queue.put(Msg({'type':'session.created'}))
  await remote.queue.put(Msg({'code':'AccessDenied.Unpurchased','message':'Access to model denied.'}))
  client=Mock();client.ws_connect=AsyncMock(return_value=remote)
  with self.assertRaisesRegex(ValueError,'AccessDenied.Unpurchased'):
   await r.connect(client,{'key':'not-real','workspace':'test','region':'beijing'},r.ASR_MODEL,r.asr_settings())
  self.assertTrue(remote.closed)
