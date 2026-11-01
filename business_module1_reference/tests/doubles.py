"""Explicit provider double for protocol/UI tests, NOT semantic validation."""
import json
from pathlib import Path

FIXTURES = json.loads((Path(__file__).parent/'fixtures/journeys.json').read_text())


class ScriptedProvider:
    def __init__(self):
        self.failure = None
        self.corrupt_quote = False
        self.corrupt_source = False
        self.calls = 0

    def readiness(self):
        return {'ready': True, 'model': 'TEST-DOUBLE', 'provider': 'scripted', 'missing': []}

    def chat(self, system, user, **kwargs):
        self.calls += 1
        if self.failure:
            raise TimeoutError('simulated timeout')
        p = json.loads(user)
        if '培训任务设计助手' in system:
            bs=p['blocks'];chosen=[b for b in bs if b['locator'].startswith('misconceptions.')][:2] or bs[:2]
            return json.dumps({'goal':p['goal'],'question':'医生问：这份课程讲的方法如何用于我提出的这个问题？','criteria':[{'id':'course_'+str(i),'label':b['title'],'expected':b['text'][:380],'source_ids':[b['id']]} for i,b in enumerate(chosen)],'end_condition':'回应本课提出的问题并保留材料限定。'},ensure_ascii=False)
        if '扮演当前培训情境' in system:
            answers=[m['text'] for m in p['transcript'] if m['role']=='药代']
            good=answers[-1] in [FIXTURES['learning'][k] for k in ['good','good_variant','negation']]+[FIXTURES['visit']['good']]
            done=good or len(answers)>=2
            return json.dumps({'complete':done,'question':'' if done else '您能具体说明刚才那句话的材料依据吗？','reason':'测试任务已完成' if done else '测试场景继续'},ensure_ascii=False)
        if '医生开场台词校对' in system:
            return json.dumps({'questions':[{'id':x['id'],'question':'上次我问过资料的适用范围，你这次能先说明有哪些依据、哪些待核实吗？'} for x in p['priorities']]},ensure_ascii=False)
        if '本次拜访的准备助手' in system:
            b=p['material']['blocks'][0]
            return json.dumps({'priorities':[{'id':'evidence_scope','title':'回应本次关切','why':'填写背景提出资料范围问题。','fact_ids':[p['facts'][0]['id']],'question':'您今天带的资料能回答什么？','criteria':[{'id':'response','label':'确认本次关切','expected':'根据本次背景回应，未知信息保留未知。','source_ids':[b['id']]}]}],'reminders':['先确认医生的具体问题。'],'unknowns':['科室实际用药需确认。']},ensure_ascii=False)
        if 'recommendations' in system:
            return json.dumps({'recommendations':[{'id':x['id'],'why':'本次任务背景中有相关待确认问题。','fact_ids':[p['facts'][0]['id']]} for x in p['options']]},ensure_ascii=False)
        if 'previous_question' in p:
            return json.dumps({'question':'这份材料如果被用于原来没有研究的人群，你会怎样回应并核实？'},ensure_ascii=False)
        answers=[(i,x['text']) for i,x in enumerate(p['transcript']) if x['role']=='药代']
        index,text=answers[-1]
        known_good=[FIXTURES['learning'][k] for k in ['good','good_variant','negation']]+[FIXTURES['visit']['good']]
        good=text in known_good
        return json.dumps({'observations':[{'criterion_id':c['id'],'status':'demonstrated' if good else 'needs_work',
                                           'quote':'编造的原话' if self.corrupt_quote else text,'turn_index':index,
                                           'reason':'回答保留了材料边界。' if good else '把未研究的范围说成已有结论，需要核实。',
                                           'source_ids':['NOT-IN-SNAPSHOT' if self.corrupt_source else (c.get('source_ids') or [p['sources'][0]['id']])[0]]}
                                          for c in p['criteria']],
                           'next_question':'' if good or len(answers)>=2 else '先别下结论，你能说明这份材料实际研究了哪些范围吗？',
                           'feedback':'这次回应说明了边界和下一步。' if good else '你直接给出了超出材料的结论，请先核对人群与指标。',
                           'focus':'换一种问法再试一次。' if good else '回看讲解，再说明材料支持和不支持的范围。'},ensure_ascii=False)
