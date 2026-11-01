"""Read-only, versioned access to the actual module-1 corpus and owned tasks.

Local source content remains unreviewed. No sample visit or invented study is
exported, and no employee/expert identity is manufactured from course content.
"""
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from knowledge import ROOT, SOURCE, LESSONS
from materials import snapshot, search_materials
from workflow import Problem

DB_PATH = next(SOURCE.glob('clinical/**/*.sqlite'))


def rows(table):
    if table not in ('med_products', 'med_questions', 'med_claims', 'med_sources'):
        raise ValueError('unsupported source table')
    with sqlite3.connect(f'file:{DB_PATH}?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        return [dict(r) for r in db.execute(f'SELECT * FROM {table}')]


def real_lesson(key):
    lesson = LESSONS.get(key)
    if not lesson or not lesson.get('source_path'):
        raise Problem('只能使用原知识库中有来源文件的课程', 400)
    return lesson


def catalog():
    bundle = json.loads(next(SOURCE.glob('clinical/**/knowledge_bundle_for_app.json')).read_text())
    courses = []
    for key, lesson in LESSONS.items():
        if not lesson.get('source_path'):
            continue
        s = snapshot(key)
        courses.append({k: s[k] for k in ('lesson_id', 'title', 'revision', 'status')}
                       | {'sourcePath': lesson['source_path'], 'sourceHash': lesson['source_hash'],
                          'references': s['references'], 'blockCount': len(s['blocks'])})
    version = hashlib.sha256(json.dumps([(c['lesson_id'], c['revision']) for c in courses]).encode()).hexdigest()
    return {'system': 'MODULE1', 'mode': 'SOURCE_CORPUS', 'version': version,
            'courses': courses, 'products': rows('med_products'), 'questions': rows('med_questions'),
            'questionDrafts': bundle['question_drafts'], 'sourceAsOf': bundle['as_of'],
            'claims': rows('med_claims'), 'sources': rows('med_sources'),
            'employeeProfile': None, 'expertHistory': [],
            'notice': '直接读取模块一原课程与SQLite知识库；保留原审核状态。未连接员工档案和真实拜访历史，不生成替身。'}


def search(lesson_id, query):
    real_lesson(lesson_id)
    material = snapshot(lesson_id)
    hits = search_materials(lesson_id, query)
    return {'system': 'MODULE1', 'lessonId': lesson_id, 'revision': material['revision'],
            'query': query, 'status': 'MATCHES_UNREVIEWED' if hits else 'NO_LOCAL_MATCH',
            'blocks': hits, 'references': material['references'],
            'medicalSupport': 'UNDETERMINED', 'medicalApproved': False}


def owned_tasks(engine, owner):
    with engine.connect() as db:
        records = []
        for table in ('sheets', 'runs'):
            for (payload,) in db.execute(f'SELECT payload FROM {table} WHERE owner=? ORDER BY rowid DESC', (owner,)):
                item = json.loads(payload)
                material = item.get('material') or {}
                lesson_id = material.get('lesson_id') or item.get('lesson_id')
                if lesson_id not in LESSONS or not LESSONS[lesson_id].get('source_path'):
                    continue
                records.append({'id': item['id'], 'kind': table, 'lessonId': lesson_id,
                                'forecastState': (item.get('forecast') or {}).get('status', 'NOT_FROZEN') if table=='sheets' else 'NOT_APPLICABLE',
                                'title': item.get('title') or item.get('visit', {}).get('title') or LESSONS[lesson_id]['title'],
                                'state': item.get('state', 'prepared')})
    return records


def export_task(engine, owner, kind, key):
    if kind not in ('sheets', 'runs'):
        raise Problem('任务类型无效')
    item = engine.load(kind, key, owner)
    material = item.get('material') or {}
    lesson_id = material.get('lesson_id') or item.get('lesson_id')
    lesson = real_lesson(lesson_id)
    if not material.get('revision') or not material.get('blocks'):
        raise Problem('原任务缺少冻结资料快照，不能用最新版补写旧计划', 409)
    options = item.get('priorities') if kind == 'sheets' else [item.get('task', {})]
    options = options or []
    if kind == 'runs' and not options[0].get('criteria'):
        options[0]['criteria'] = item.get('criteria', [])
    if not any(o.get('criteria') for o in options):
        raise Problem('原任务没有可导出的观察标准', 409)
    return {'system': 'MODULE1', 'sourceKind': kind, 'sourceTaskId': key,
            'lessonId': lesson_id, 'title': lesson['title'], 'sourcePath': lesson['source_path'],
            'sourceHash': lesson['source_hash'], 'material': material, 'options': options,
            'candidatePoolKnown': bool(kind=='sheets' and item.get('forecast',{}).get('status')=='FROZEN'),
            'forecast': item.get('forecast') if kind=='sheets' else None, 'expertId': None,
            'consumedEvolutionVersions': item.get('consumed_evolution_versions', []),
            'consumedMethodVersions': item.get('consumed_method_versions', []),
            'review': item.get('review'), 'transcript': item.get('transcript', []),
            'attempt': item.get('attempt', 1),
            'frozenAt': datetime.fromtimestamp(item['created_at'],timezone.utc).isoformat() if isinstance(item.get('created_at'),(int,float)) else item.get('createdAt'),
            'observedAt': datetime.fromtimestamp(item['updated_at'],timezone.utc).isoformat() if isinstance(item.get('updated_at'),(int,float)) else None,
            'notice': '来自本人模块一任务的原快照。仅拜访前确认冻结的系统候选集可用于比较；它并非所有可能问题的全集，专家身份未独立核验。'}
