#!/usr/bin/env python3
"""Read only M1's *actual* fictional lesson + option definitions.

Produces a TEST_ONLY handoff fixture; sheet and selectedOptionIds are explicitly
synthetic for integration tests, never claimed to be persisted Engine.prepare data.
Requires only standard library + M1 knowledge.py and bundled SQLite; no API.
"""
from pathlib import Path
import argparse, importlib.util, json, sys
from datetime import datetime, timezone

parser = argparse.ArgumentParser()
parser.add_argument('--module1', required=True, help='M1 01_当前项目 root')
parser.add_argument('--out', required=True)
args = parser.parse_args()
root=Path(args.module1).resolve()
sys.path.insert(0,str(root))
from knowledge import LESSONS, VISITS
lesson=LESSONS['demo-evidence']; visit=VISITS['demo-visit']
assert lesson['status']=='fictional_test_material'
assert visit['lesson_id']==lesson['id']
assert all(s['status']=='fictional_test_material' and s.get('text') for s in lesson['sources'])
blocks=[]
for i,sect in enumerate(lesson['sections']):
    blocks.append({'id':f"{lesson['id']}:sections.{i}", 'title':sect['title'], 'text':sect['body'], 'status':'fictional_test_material'})
# These are original M1's available options; *selected* subset is a controlled
# fictional scenario, not an assertion about a historical rehearsal.
selected=['needs','followup']
packet={
  'kind':'M1_FICTIONAL_BRIDGE_V1','usage':'TEST_ONLY',
  'taskId':'m1-demo-prep-001','researchId':'m1-demo-c17', 'repId':'rep-demo-a','expertId':'expert-demo-zhou',
  'preparedAt':'2026-10-30T09:00:00Z',
  'lesson':{'id':lesson['id'],'title':lesson['title'],'status':lesson['status'],'sources':lesson['sources'],'blocks':blocks},
  'visit':{'id':visit['id'],'title':visit['title'],'lesson_id':visit['lesson_id'],'options':visit['options']},
  'sheet':{'id':'fictional-sheet-001','visit_id':visit['id'],'priorities':visit['options'],'created_at':1793350800},
  'selectedOptionIds':selected,
}
out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(packet,ensure_ascii=False,indent=2),encoding='utf8')
print(f'Exported TEST_ONLY handoff from M1: {len(lesson["sources"])} authored sources, {len(blocks)} material blocks, {len(visit["options"])} options; selected = {selected}')
