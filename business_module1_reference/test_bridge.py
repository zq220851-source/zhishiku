"""Test-only, owner-scoped M2 candidate adoption and M3 review inbox.

None of this grants medical approval. No changes to original sheet or LESSONS.
"""
import copy, hashlib, json, secrets, time
from datetime import datetime, timezone
from knowledge import get_lesson
from workflow import Problem


def compact(data):
    return json.dumps(data, ensure_ascii=False, separators=(',', ':'))


def fingerprint(data):
    return hashlib.sha256(compact(data).encode('utf-8')).hexdigest()


def sheet_hash(sheet):
    return hashlib.sha256(json.dumps(sheet, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()


def freeze_user_selection_for_test(engine, owner, source_sheet, selected):
    """Simulate a rep explicitly choosing a subset from Engine.prepare's real options."""
    if not isinstance(selected, list) or not selected or len(selected)>len(source_sheet['priorities']) or len(set(selected)) != len(selected):
        raise Problem('请选择不重复的已生成备选题目')
    options={x['id']:x for x in source_sheet['priorities']}
    if any(x not in options for x in selected):
        raise Problem('准备单未提供所选的场景')
    frozen=copy.deepcopy(source_sheet)
    frozen['id']='test-selected-'+secrets.token_hex(12)
    frozen['priorities']=[copy.deepcopy(options[x]) for x in selected]
    frozen['testSelection']={'status':'REP_SELECTED_FIXTURE','selectedOptionIds':[x for x in selected],
                             'sourceUnselectedSheetId':source_sheet['id']}
    frozen['method']='由测试员工从模块1生成的备选准备重点中明确选择，不是模型最终排序结论'
    engine.save('sheets',frozen,owner)
    return frozen


def apply_reviewed_test_candidate(engine, owner, source_sheet_id, candidate, decision):
    source = engine.load('sheets', source_sheet_id, owner)
    if get_lesson(source['visit']['lesson_id'])['status'] != 'fictional_test_material':
        raise Problem('只允许虚构课程使用联调入口', 403)
    if not isinstance(candidate, dict) or candidate.get('usage') != 'TEST_ONLY' or candidate.get('status') != 'CANDIDATE_NOT_APPLIED':
        raise Problem('尚未形成有效的测试选题候选')
    if candidate.get('sourceSheetHash') != sheet_hash(source):
        raise Problem('候选绑定的旧准备单与实际准备单不一致', 409)
    if not isinstance(candidate.get('sourceSnapshotHash'), str) or len(candidate['sourceSnapshotHash']) != 64:
        raise Problem('未绑定模块2冻结任务')
    actual = {o['id']: o for o in source['visit']['options']}
    original = [p['id'] for p in source['priorities']]
    selected = candidate.get('selectedOptionIds')
    if not isinstance(selected, list) or not selected or len(selected) > len(original) or len(selected) != len(set(selected)) or any(x not in actual for x in selected):
        raise Problem('选择的题目不合法')
    if not isinstance(decision, dict) or decision.get('action') != 'ADOPT_TEST_ONLY' or decision.get('status') != 'REVIEWED_TEST_ONLY' or decision.get('candidateHash') != fingerprint(candidate) or not isinstance(decision.get('reviewer'), str) or not decision['reviewer'].startswith('fixture-reviewer-'):
        raise Problem('测试审核没有绑定这份完整候选', 403)
    reviewed_at = decision.get('reviewedAt')
    if not isinstance(reviewed_at, str):
        raise Problem('缺审核时间')
    try:
        reviewed_timestamp = datetime.fromisoformat(reviewed_at.replace('Z', '+00:00')).timestamp()
    except ValueError:
        raise Problem('审核时间无效')
    if reviewed_timestamp < source['created_at']:
        raise Problem('不能在准备单创建前审核')
    if not isinstance(decision.get('reviewId'), str) or len(decision['reviewId']) < 10:
        raise Problem('缺少审查编号')
    # Immutable adoption receipt: reusing a review ID cannot create multiple new plans.
    new_id = 'test-followup-' + hashlib.sha256((source_sheet_id + ':' + decision['reviewId']).encode()).hexdigest()[:24]
    with engine.connect() as db:
        row = db.execute('SELECT owner,payload FROM sheets WHERE id=?', (new_id,)).fetchone()
    if row:
        if row[0] != owner:
            raise Problem('记录已被其他身份使用', 409)
        found = json.loads(row[1])
        if found.get('reviewReceipt', {}).get('candidateHash') != decision['candidateHash']:
            raise Problem('审核编号不可复用到另一个候选', 409)
        return found
    out = copy.deepcopy(source)
    out['id'] = new_id
    out['created_at'] = max(time.time(), reviewed_timestamp)
    out['priorities'] = [copy.deepcopy(actual[x]) for x in selected]
    out['practice_results'] = []
    out['method'] = '模块2已审核的测试候选，仅用于虚构任务；未替换正式预测策略'
    out['reviewReceipt'] = {'status': 'TEST_APPLIED_TO_NEW_SHEET', 'sourceSheetId': source_sheet_id,
                            'sourceSheetHash': sheet_hash(source), 'sourceSnapshotHash': candidate['sourceSnapshotHash'],
                            'candidateHash': decision['candidateHash'], 'reviewId': decision['reviewId'],
                            'reviewedAt': reviewed_at, 'reviewer': decision['reviewer'],
                            'added': [x for x in selected if x not in original],
                            'displaced': [x for x in original if x not in selected]}
    out['notice'] = '测试环境内经人工确认的新准备单；未获医学批准；原始准备单不变。'
    engine.save('sheets', out, owner)
    return out


def review_external_test_candidate(inbox, source_id, reviewer, approval, evidence_hash):
    """Produce a test knowledge-review decision; cannot alter the clinical knowledge store."""
    if not isinstance(inbox, dict) or inbox.get('kind') != 'M3_TO_M1_REVIEW_INBOX_V1' or inbox.get('usage') != 'TEST_ONLY' or inbox.get('knowledgeGapResolved') is not False:
        raise Problem('模块3资料队列格式不正确')
    candidates = [c for c in inbox.get('candidates', []) if c.get('sourceId') == source_id]
    if len(candidates) != 1 or candidates[0].get('approvalStatus') != 'PENDING_MEDICAL_REVIEW' or candidates[0].get('appliedToTraining') is not False:
        raise Problem('只能审核尚未使用的资料候选')
    item = candidates[0]
    if evidence_hash != item.get('sourceVersion') or not isinstance(reviewer, str) or not reviewer.startswith('fixture-medical-reviewer-'):
        raise Problem('审核必须核对来源版本及测试审核员身份', 403)
    if approval not in ('ACCEPT_FOR_TEST_READING', 'REJECT'):
        raise Problem('没有正式医学批准权限', 403)
    return {'kind': 'M3_M1_TEST_REVIEW_DECISION_V1', 'usage': 'TEST_ONLY',
            'sourceId': item['sourceId'], 'sourceVersion': evidence_hash,
            'reviewer': reviewer, 'decision': approval,
            'canUseForTestReading': approval == 'ACCEPT_FOR_TEST_READING',
            'canUseAsMedicalKnowledge': False, 'canUseForScoring': False,
            'canUpdateKnowledgeVersion': False,
            'requestedCapabilityId': inbox['requestedCapabilityId'],
            'decisionHash': fingerprint({'inboxId': inbox['requestId'], 'sourceId': source_id,
                                         'sourceVersion': evidence_hash, 'approval': approval}),
            'note': '测试审核只允许查看外部资讯，不产生医学事实认证或知识库版本升级。'}
