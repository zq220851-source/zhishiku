#!/usr/bin/env python3
"""Independent JSON-output gate. Reads artifacts, not TypeScript business code."""
from pathlib import Path
import json,sys
root=Path(__file__).resolve().parents[4]
f=lambda name:json.loads((root/'shared_exchange'/name).read_text(encoding='utf8'))
a=f('three-module-results.json');b=f('module3-external-candidates.json');c=f('module3-to-module2-search.json');d=f('module3-to-module1-review-queue.json');e=f('module2-to-module1-next-preparation.json');q=f('module2-to-module3-search.json')
checks={
 '三模块来源有清楚标识': a['kind']=='THREE_MODULE_TEST_ONLY_RESULT' and b['sourceSystem']=='MEDREP_DAILY' and a['module1']['lessonId']=='demo-evidence',
 '模块1原准备仍是两项':a['module1']['selectedBefore']==['needs','followup'],
 '冻结标识存在':len(a['module1']['snapshotHash'])==64,
 '两次训练证据实际更新':a['module2']['firstPractice'][0]['result']=='GAP' and a['module2']['secondPractice'][0]['result']=='SATISFIED',
 '五资产存在且不重复':set(x['kind'] for x in a['module2']['assets'])=={'PERSONAL_SKILL','FORECAST','KNOWLEDGE_COVERAGE','EXPERT_OBSERVATION','COHORT_EVENT'},
 '知识检索失败没有被误认成知识缺失已证实':a['module2']['knowledge'][0]['recommendation']=='REVIEW_RETRIEVAL',
 '真实模块3源码产出的资讯带原始来源':len(b['sourceItems'])>=3 and all(x['sourceUrl'].startswith('https://') and x['sourceMode']=='sample' for x in b['sourceItems']),
 '模块2请求与模块3响应一一对应':q['requestId']==c['requestId']==d['requestId'],
 '搜索结果确实是模块3来源库条目':all(any(x['sourceId']==y['sourceId'] and x['contentHash']==y['contentHash'] for y in b['sourceItems']) for x in c['matches']),
 '检索不是实时联网':c['status']=='LOCAL_SAMPLE_MATCHES_NOT_VERIFIED',
 '所有外部资料均未获医学审核':all(x['approval']=='UNREVIEWED' for x in b['sourceItems']) and all(x['approvalStatus']=='PENDING_MEDICAL_REVIEW' for x in d['candidates']),
 '外部资料未自动进入模块1训练':not d['knowledgeGapResolved'] and all(not x['appliedToTraining'] for x in d['candidates']),
 '公开学术线索未绑定实际专家':b['academicExample']['linkedModule1ExpertId'] is None and a['module3']['publicAcademicIdentity']=='NOT_VERIFIED',
 '新选题有理由且记录旧选项':e['sourceSnapshotHash']==a['module1']['snapshotHash'] and e['addedOptionIds']==['evidence_scope'] and e['displacedOptionIds']==['followup'],
 '新选题未自动执行':e['status']=='CANDIDATE_NOT_APPLIED',
 '没有把下一轮改变冒充原历史准备':a['module2']['nextPreparation']['before']!=a['module2']['nextPreparation']['after'],
 '选题依据来自过去的两次虚构拜访':set(e['evidenceVisitIds'])=={'three-module-fictional-visit-1','three-module-fictional-visit-2'},
 '5种资产的群体模式没有变成公司结论':all(x['status']=='DESCRIPTIVE_ONLY' for x in a['module2']['cohort']),
 '专家观察不被写成稳定偏好':all(x['status']=='SINGLE_REPORTED_OBSERVATION' for x in a['module2']['experts']),
}
report={'scope':'TEST_ONLY independent JSON output audit','total':len(checks),'passed':sum(checks.values()),'failed':[k for k,v in checks.items() if not v], 'checks':checks}
(root/'shared_exchange/independent-three-module-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'passed':report['passed'],'total':report['total'],'failed':report['failed']},ensure_ascii=False))
if report['failed']:sys.exit(1)
