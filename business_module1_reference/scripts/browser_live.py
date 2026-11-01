"""Real browser -> HTTP app -> real model -> persisted preparation sheet."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright,expect
expect.set_options(timeout=90000)
from tests.doubles import FIXTURES as F
out=Path('test-results');out.mkdir(exist_ok=True)
report={'kind':'real_browser_real_model','passed':False,'human_microphone_verified':False}
try:
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1280,'height':960})
  page.set_default_timeout(90000);errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  report['stage']='connect'
  page.goto('http://127.0.0.1:8791');expect(page.locator('#model-status')).to_contain_text('模型已连接')
  report['stage']='learning'
  page.locator('#start-learn').click();page.locator('#answer').fill(F['learning']['good']);page.locator('#answer-btn').click()
  expect(page.locator('#feedback')).to_contain_text('本次已体现')
  expect(page.locator('#retry-btn')).to_be_visible()
  page.screenshot(path=str(out/'live-learning.png'),full_page=True)
  report['stage']='visit'
  page.locator('#visit-tab').click();page.locator('#prepare-btn').click()
  expect(page.locator('#sheet')).to_contain_text('模型结合已填背景')
  priority=page.locator('[data-practice="evidence_scope"]')
  if priority.count()==0:priority=page.locator('[data-practice]').first
  priority.click();page.locator('#answer').fill(F['visit']['good']);page.locator('#answer-btn').click()
  expect(page.locator('#feedback')).to_contain_text('本次已体现')
  if page.locator('#answer-form').is_visible():
   page.locator('#answer').fill(F['visit']['good']);page.locator('#answer-btn').click();expect(page.locator('#retry-btn')).to_be_visible()
  page.locator('#return-sheet').click();expect(page.locator('#sheet')).to_contain_text('试练后补充')
  report['stage']='reload'
  page.reload();page.locator('#visit-tab').click();expect(page.locator('#sheet')).to_contain_text('试练后补充')
  page.screenshot(path=str(out/'live-visit.png'),full_page=True)
  assert not errors,errors
  report.update(passed=True,journeys=['learning_answer_feedback','visit_preparation_practice_update_reload'],console_errors=errors)
  browser.close()
except Exception as e:
 report.update(error_type=type(e).__name__)
(out/'browser-live.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(('PASS' if report['passed'] else 'FAIL')+' real browser + real model',flush=True)
raise SystemExit(0 if report['passed'] else 1)
