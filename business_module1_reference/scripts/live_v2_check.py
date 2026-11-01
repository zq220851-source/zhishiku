"""Real model smoke check with authored responses; not medical validation."""
import argparse,json,sys,tempfile,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
parser=argparse.ArgumentParser();parser.add_argument('--config-from',required=True);parser.add_argument('--visit-only',action='store_true');args=parser.parse_args()
from scripts.credentials import configure
configure(args.config_from)
from app import RemoteDoctorProvider
from workflow import Engine
from knowledge import ROOT
out=ROOT/'test-results/v2';out.mkdir(parents=True,exist_ok=True)
provider=RemoteDoctorProvider();results=[]
original_chat=provider.chat
def capture_chat(system,user,**kw):
 raw=original_chat(system,user,**kw)
 if '本次拜访的准备助手' in system:
  (out/'preparation-raw.json').write_text(json.dumps({'input':json.loads(user),'output':raw},ensure_ascii=False,indent=2))
 return raw
provider.chat=capture_chat
answers={
 'bounded':'这节课提供的是读研究的方法，没有给出具体研究原文和数值。我先核对有没有同期对照、主要终点、入组人群以及安全性随访。单臂结果不能直接拿来跨研究比较，PFS改善不能直接说成OS获益。EGFR结果还没回来不能当成阴性。具体研究覆盖谁，我需要查研究原文和方案，并结合最新说明书向医学信息确认后反馈。',
 'overclaim':'没问题，EGFR没回来就是阴性，PFS改善肯定说明总生存也更好。我们直接按全部人群推广，不用再核实。',
}
with tempfile.TemporaryDirectory() as td:
 e=Engine(Path(td)/'live.db',provider);owner='fictional-v2-smoke'
 for label,answer in ([] if args.visit_only else answers.items()):
  start=time.time();r=e.create({'mode':'learn','lesson_id':'D-NSCLC__CE'},owner)
  r=e.answer(r['id'],{'answer':answer,'revision':r['revision'],'request_id':'live-v2-'+label},owner)
  if r['state']=='active':r=e.finish(r['id'],owner)
  assert r['state']=='review' and r['review']['medical_accuracy']=='NA'
  allowed={b['id'] for b in r['material']['blocks']}
  assert all(set(o['source_ids'])<=allowed for o in r['review']['observations'])
  results.append({'case':label,'elapsed_seconds':round(time.time()-start,2),'run':r})
  (out/'live-model.json').write_text(json.dumps({'model':provider.readiness()['model'],'cases':results,'limitation':'Original course remains unreviewed; these calls test grounding and flow, not medical correctness.'},ensure_ascii=False,indent=2))
  print(label,r['state'],[(x['status']) for x in r['review']['observations']],flush=True)
 context={'doctor':'A医院周医生（虚构测试）','goal':'确认医生关心的研究人群问题，并约定需要核实的资料。','facts':'虚构背景记录：上次医生问过EGFR检测未回报的人群能否外推。\n虚构安排：本次5分钟；科室实际用药未知。','lesson_id':'D-NSCLC__CE'}
 s=e.prepare('custom',owner,context)
 assert s['material']['lesson_id']=='D-NSCLC__CE' and s['practice_results']==[]
 r=e.create({'mode':'visit','sheet_id':s['id'],'option_id':s['priorities'][0]['id']},owner)
 r=e.answer(r['id'],{'answer':answers['bounded'],'revision':0,'request_id':'live-visit-v2'},owner)
 if r['state']=='active':r=e.finish(r['id'],owner)
 after=e.load('sheets',s['id'],owner);assert len(after['practice_results'])==1
 (out/'live-visit.json').write_text(json.dumps({'sheet_before':s,'run':r,'sheet_after':after},ensure_ascii=False,indent=2))
 print('visit',len(s['priorities']),'priorities; same sheet updated',flush=True)
