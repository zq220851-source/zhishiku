import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from doctor_engine import DoctorState
from innovent_scenarios import build_scenarios


class PressureScenarioTests(unittest.TestCase):
    def test_same_facts_and_independent_persona(self):
        scenes = build_scenarios()
        normal, pressure = scenes['io_first'], scenes['io_first_pressure']
        self.assertEqual(normal['facts'], pressure['facts'])
        self.assertEqual(normal['sources'], pressure['sources'])
        self.assertEqual(normal['profile_id'], pressure['profile_id'])
        pressure['public']['known_concern'] = 'changed'
        self.assertNotEqual(normal['public']['known_concern'], 'changed')
        self.assertFalse(DoctorState(normal).pressure)

    def test_pressure_is_not_rewritten_to_polite_and_closes(self):
        doctor = DoctorState(build_scenarios()['io_first_pressure'])
        with patch('doctor_engine.RemoteDoctorProvider') as factory:
            provider = factory.return_value
            provider.provider = 'credits'
            provider.chat.return_value = '别绕弯，明天把资料带来。'
            answer, _, _ = doctor.respond('我先不打扰您了', [{'role': '药代', 'text': '我先不打扰您了'}])
            self.assertEqual(provider.chat.call_count, 1)
            self.assertIn('别绕弯', answer)
            self.assertTrue(doctor.finished)
            prompt = provider.chat.call_args.args[0]
            self.assertIn('很凶、不客气', prompt)
            self.assertNotIn('即使时间紧，也保持礼貌', prompt)

    def test_normal_visit_keeps_polite_rewrite(self):
        with patch('doctor_engine.RemoteDoctorProvider') as factory:
            provider = factory.return_value
            provider.provider = 'credits'
            provider.chat.side_effect = ['别绕弯，讲重点。', '请先说重点。']
            answer, _, _ = DoctorState(build_scenarios()['io_first']).respond('你好', [{'role': '药代', 'text': '你好'}])
            self.assertEqual(answer, '请先说重点。')
            self.assertEqual(provider.chat.call_count, 2)
            self.assertNotIn('这是用户选择的高压拜访角色', provider.chat.call_args_list[0].args[0])


if __name__ == '__main__':
    unittest.main()
