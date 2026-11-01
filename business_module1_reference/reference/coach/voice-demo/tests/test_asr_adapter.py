import io,json,sys,unittest,urllib.error
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from asr_provider import transcribe_whisper
from remote_provider import RemoteAPIError
class Provider:
 url='https://api.openai-next.com/v1/chat/completions';key='unit-test-placeholder'
class AdapterTest(unittest.TestCase):
 def test_multipart_audio_and_simplified_result(self):
  def receive(request,*args,**kwargs):
   self.assertEqual(request.full_url,'https://api.openai-next.com/v1/audio/transcriptions')
   self.assertIn(b'name="model"',request.data);self.assertIn(b'whisper-1',request.data);self.assertIn(b'audio-test-bytes',request.data)
   return json.dumps({'text':'许医生您好。'}).encode()
  with patch('asr_provider.request_bytes',side_effect=receive):self.assertEqual(transcribe_whisper(b'audio-test-bytes',Provider()),'许医生您好。')
 def test_rate_limit_has_actionable_error_and_does_not_return_partial_text(self):
  error=urllib.error.HTTPError(Provider.url,429,'limited',{},io.BytesIO(b'{}'))
  with patch('asr_provider.request_bytes',side_effect=error):
   with self.assertRaisesRegex(RemoteAPIError,'限流'):transcribe_whisper(b'audio',Provider())
 def test_invalid_text_is_not_submitted(self):
  with patch('asr_provider.request_bytes',return_value=b'{"text":123}'):
   with self.assertRaises(RemoteAPIError):transcribe_whisper(b'audio',Provider())
