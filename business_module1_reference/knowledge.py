"""Keep original structured assets intact. Read and map; never approve them."""
from pathlib import Path
import json, hashlib, sqlite3

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'reference/coach'


def demo_lesson():
    return {
        'id': 'demo-evidence', 'title': '把研究结论讲到证据允许的范围',
        'duration': '约 5 分钟', 'status': 'fictional_test_material',
        'notice': '虚构培训材料，用于验证软件流程；不是医学事实或正式评分标准。',
        'goal': '面对证据追问，说明材料支持什么、没有说明什么，并给出具体核实动作。',
        'sections': [
            {'title': '先看研究实际说明了什么', 'body': '演示研究 C-17 仅观察了虚构的 A 类人群，记录指标 X；没有同期比较组，也未测量指标 Y。材料不能用于真实患者或产品判断。'},
            {'title': '回应时保留限定条件', 'body': '先回答医生的问题，再说研究对象、测量指标与局限。没有测量的结果不能补成已有结论，没有比较组不能声称优于其他方案。'},
            {'title': '缺信息时把下一步说具体', 'body': '明确哪一点尚不知道、查哪份资料、如何再反馈。说“我以后给您”只代表计划，不能当作已经提供。'},
        ],
        'sources': [{'id': 'DEMO-C17', 'title': '虚构研究 C-17 · 软件测试夹具', 'locator': '材料第1—3条',
                     'text': '仅A类人群；观察指标X；无同期比较组；未测量Y；不用于真实医疗判断。', 'status': 'fictional_test_material'}],
        'checks': [],
        'skills': ['evidence_scope', 'clear_response', 'followup'],
        'practice': {
            'question': '您这份材料能说明什么？如果换成人群 B，或者说指标 Y 也更好，有依据吗？',
            'criteria': [
                {'id': 'scope', 'label': '说明人群与指标范围', 'expected': '限定为A类人群和指标X，不外推B或Y'},
                {'id': 'comparison', 'label': '说明比较证据的局限', 'expected': '无同期比较组，不宣称比其他方案更好'},
                {'id': 'next', 'label': '对未知给出具体核实动作', 'expected': '清楚说明需查原始资料，并安排反馈；未完成的事只说计划'},
            ], 'medical_scoring': False,
        },
    }


def catalog():
    lessons = [demo_lesson()]
    bridge = json.loads((SOURCE / 'skill-taxonomy/course-skill-bridge.json').read_text())['course_to_skill']
    # Public/source-only deployments intentionally do not ship licensed clinical SQLite.
    # Allow the *clearly fictional* demo lesson and visit-communication to load;
    # no real clinical course is returned until the organization supplies lawful content.
    clinical_dbs = sorted(SOURCE.glob('clinical/**/*.sqlite'))
    if not clinical_dbs:
        return {x['id']: x for x in lessons}
    dbpath = clinical_dbs[0]
    db = sqlite3.connect(f'file:{dbpath}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    for dirname, kind in [('course-specs', '疾病基础'), ('course-specs-tl', '治疗格局'), ('course-specs-ce', '证据解读')]:
        for path in sorted((SOURCE / dirname).glob('*.json')):
            d = json.loads(path.read_text())
            cid = path.stem.split('__')[0]
            dim = {'course-specs':'disease_foundation','course-specs-tl':'treatment_landscape','course-specs-ce':'clinical_evidence'}[dirname]
            condition = db.execute('SELECT c.*,s.title as source_title,s.url as source_url,s.asof_date FROM clinical_conditions c LEFT JOIN clinical_sources s ON c.source_id=s.source_id WHERE c.condition_id=?',(cid,)).fetchone()
            mapping = bridge.get(cid+'|'+dim, [])
            lessons.append({'id': path.stem, 'title': d.get('meta', {}).get('title', path.stem),
                            'duration': d.get('meta', {}).get('duration', ''), 'kind': kind,
                            'status': 'pending_medical_review', 'notice': '原交接包候选课程，未经医学审核；仅作内部学习设计参考，医学对错不自动评分。',
                            'goal': d.get('goal', ''),
                            'content': d, 'condition_id': cid,
                            'sections': [{'title': x.get('title', ''), 'body': x.get('body', '')} for x in d.get('steps', [])] +
                                        [{'title': '常见误区：' + x['myth'], 'body': x['correction']} for x in d.get('misconceptions', [])],
                            'sources': [{'id': f'{path.stem}-SRC-{i}', 'title': x.get('label', ''), 'url': x.get('url', ''),
                                         'locator': x.get('detail', ''), 'status': 'pending_medical_review'} for i, x in enumerate(d.get('sources', []))],
                            'checks': d.get('checks', []), 'skills': [path.stem],
                            'capability_mapping': mapping,
                            'knowledge_context': dict(condition) if condition else None,
                            'practice': {'question': d.get('hero', {}).get('question', d.get('recall', {}).get('prompt', '请用自己的话解释本课重点。')),
                                         'criteria': [
                                             {'id': 'response', 'label': '先回应对方的具体问题', 'expected': '回应所问，必要时澄清，不背无关内容'},
                                             {'id': 'boundary', 'label': '明确资料边界与未知', 'expected': '指出来源和需要核实的部分，不编造医学事实'},
                                         ], 'medical_scoring': False},
                            'source_path': str(path.relative_to(ROOT)),
                            'source_hash': hashlib.sha256(path.read_bytes()).hexdigest()})
            if condition:
                lessons[-1]['sections'].append({'title':'原知识库标注的训练范围','body':condition['competency_scope'] + '。' + (condition['relationship_note'] or '')})
                lessons[-1]['sources'].append({'id':condition['source_id'],'title':condition['source_title'],
                                               'url':condition['source_url'],'locator':'clinical_conditions / '+cid+' · '+str(condition['asof_date']),
                                               'status':condition['medical_review']})
    db.close()
    return {x['id']: x for x in lessons}


LESSONS = catalog()
LESSONS['visit-communication'] = {
    'id': 'visit-communication', 'title': '访前沟通准备', 'status': 'pending_medical_review',
    'goal': '回应具体关切，明确不知道的部分与核实动作。', 'duration': '按需',
    'notice': '仅评价沟通行为，不判断用户提供的医学资料是否正确。',
    'sections': [{'title': '回应与核实', 'body': '先确认问题，再回答有依据的部分；未知信息保留未知，并说明查证与反馈安排。'}],
    'sources': [{'id': 'SCORECARD-D2', 'title': '原包候选评分卡 D2', 'locator': '回应清晰与双向互动', 'status': 'pending_review'},
                {'id': 'SCORECARD-D5', 'title': '原包候选评分卡 D5', 'locator': '证据、风险与不确定性', 'status': 'pending_review'}],
    'skills': ['clear_response'], 'checks': [],
    'practice': {'question': '请回应对方关切。', 'criteria': [
        {'id': 'response', 'label': '回应具体问题', 'expected': '先确认所问，再回应'},
        {'id': 'boundary', 'label': '明确未知与核实', 'expected': '不编造未知事实，说明查证动作'}], 'medical_scoring': False},
}

# Explicitly fictional visit context. Unknown hospital usage is not filled by AI.
VISITS = {
 'demo-visit': {
    'id': 'demo-visit', 'title': '周医生 · 演示研究资料交流',
    'doctor': '周医生（虚构）', 'hospital': '演示医院（虚构）',
    'goal': '确认医生关注的问题，回应研究资料的范围，并约定需要核实的资料。',
    'facts': [
        {'id': 'VIS-1', 'text': '本次约 5 分钟，医生上次问过研究人群能否对应科室情况。', 'source': '虚构拜访背景', 'status': 'fictional'},
        {'id': 'VIS-2', 'text': '本次携带演示研究 C-17；科室实际用药情况未知，需询问确认。', 'source': '虚构任务说明', 'status': 'fictional'},
    ],
    'lesson_id': 'demo-evidence', 'topics': ['evidence_scope', 'needs', 'followup'],
    'options': [
        {'id': 'needs', 'title': '开场后确认真正关切', 'why': '会面时间短，先弄清医生想解决什么。',
         'question': '我只有几分钟。你今天想跟我聊什么？', 'skills': ['needs'], 'fact_ids': ['VIS-1'],
         'criteria': [{'id': 'focus', 'label': '简短说明来意并确认关切', 'expected': '说明来意，确认医生想了解的人群问题，不直接长篇介绍'}]},
        {'id': 'evidence_scope', 'title': '回应研究适用范围', 'why': '医生上次已提出人群相关疑问，是有背景依据的准备重点。',
         'question': '你这份研究只看了A类人群吧？能直接说明B类人群，或者指标Y也更好吗？',
         'skills': ['evidence_scope'], 'fact_ids': ['VIS-1', 'VIS-2'], 'criteria': demo_lesson()['practice']['criteria']},
        {'id': 'followup', 'title': '把待核实事项约定清楚', 'why': '本次资料可能不能回答所有问题，需要清楚约定下一步。',
         'question': '这部分你还没确认，那接下来具体怎么处理？', 'skills': ['followup'], 'fact_ids': ['VIS-2'],
         'criteria': [{'id': 'next', 'label': '区分计划和已完成动作', 'expected': '说明待查事项、查证途径与反馈安排，不把承诺当作已完成'}]},
    ],
 }
}


def get_lesson(key):
    if key not in LESSONS:
        raise ValueError('课程不存在')
    return LESSONS[key]
