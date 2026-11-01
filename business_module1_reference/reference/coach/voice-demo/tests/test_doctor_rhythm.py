import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from doctor_engine import DoctorState,SCENARIOS
class RhythmTests(unittest.TestCase):
 def test_semicolon_and_thinking_pause_keep_one_speech_unit(self):
  text='这部分我还想看看；具体的人群……需要再核实。'
  with patch('doctor_engine.RemoteDoctorProvider') as factory:
   p=factory.return_value;p.provider='credits'
   def chat(system,user,**kw):
    for c in text:kw['on_delta'](c)
    return text
   p.chat.side_effect=chat;parts=[]
   answer,_,_=DoctorState(SCENARIOS['busy_visit']).respond('我把资料带来了',[{'role':'药代','text':'我把资料带来了'}],on_sentence=parts.append)
   self.assertEqual(parts,[text]);self.assertEqual(answer,text)
if __name__=='__main__':unittest.main()
