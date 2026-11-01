"""Actual browser UI journeys against real HTTP app + explicit model double."""
import json,sys,tempfile,threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright,expect
from app import make_server
from tests.doubles import ScriptedProvider,FIXTURES as F

out=Path('test-results');out.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as td:
    provider=ScriptedProvider();server=make_server(0,Path(td)/'ui.sqlite',provider,True)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True,args=['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream'])
            context=browser.new_context(viewport={'width':1280,'height':960},permissions=['microphone'])
            page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(f'http://127.0.0.1:{server.server_port}')
            expect(page.locator('#lesson-select option')).to_have_count(72)
            page.screenshot(path=str(out/'learning-desktop.png'),full_page=True)
            page.get_by_role('button',name='用医生的问题练一下').click()
            expect(page.locator('#answer-form')).to_be_visible()
            page.locator('#answer').fill(F['learning']['wrong']);page.locator('#answer-btn').click()
            expect(page.locator('#feedback')).to_contain_text('还有遗漏')
            page.locator('#answer').fill(F['learning']['followup_wrong']);page.locator('#answer-btn').click()
            expect(page.locator('#retry-btn')).to_be_visible()
            page.locator('#support-btn').click();expect(page.locator('#support')).to_be_visible()
            page.locator('#retry-btn').click();expect(page.locator('#practice-meta')).to_contain_text('第 2 次')
            page.locator('#answer').fill(F['learning']['good_variant']);page.locator('#answer-btn').click()
            expect(page.locator('#feedback')).to_contain_text('本次已体现')
            page.screenshot(path=str(out/'learning-feedback.png'),full_page=True)
            page.locator('#visit-tab').click();page.locator('#prepare-btn').click()
            expect(page.locator('#sheet')).to_contain_text('科室实际用药情况未知')
            page.locator('[data-practice="evidence_scope"]').click()
            page.locator('#answer').fill(F['visit']['good']);page.locator('#answer-btn').click()
            expect(page.locator('#return-sheet')).to_be_visible();page.locator('#return-sheet').click()
            expect(page.locator('#sheet')).to_contain_text('试练后补充')
            page.reload();page.locator('#visit-tab').click();expect(page.locator('#sheet')).to_contain_text('试练后补充')
            page.screenshot(path=str(out/'visit-desktop.png'),full_page=True)
            # Custom input with HTML is inert text, including after model preparation.
            page.locator('#visit-select').select_option('custom')
            page.locator('#doctor').fill('<img src=x onerror=alert(1)>（虚构）')
            page.locator('#goal').fill(F['visit']['custom_context']['goal'])
            page.locator('#visit-facts').fill(F['visit']['custom_context']['facts']);page.locator('#prepare-btn').click()
            expect(page.locator('#sheet')).to_contain_text('<img src=x')
            assert page.locator('#sheet img').count()==0
            # Failure recovery is exercised through actual browser controls.
            page.locator('#learn-tab').click();page.locator('#start-learn').click()
            provider.failure=True
            page.locator('#answer').fill(F['learning']['good']);page.locator('#answer-btn').click()
            expect(page.locator('#retry-error')).to_be_visible()
            provider.failure=False;page.locator('#retry-feedback').click()
            expect(page.locator('#feedback')).to_contain_text('本次已体现')
            # Correction must invalidate old feedback and allow resubmission.
            page.once('dialog',lambda dialog:dialog.accept(F['learning']['wrong']))
            page.locator('#correct-btn').click();expect(page.locator('#retry-error')).to_be_visible()
            expect(page.locator('#feedback')).not_to_contain_text('本次已体现')
            page.locator('#retry-feedback').click();expect(page.locator('#feedback')).to_contain_text('还有遗漏')
            page.locator('#history-tab').click();expect(page.locator('.history-row')).to_have_count(3)
            page.locator('#learn-tab').click();page.locator('#start-learn').click()
            page.locator('#record-btn').click();expect(page.locator('#record-btn')).to_contain_text('停止录音')
            page.evaluate('window.testTrack=state.recording.stream.getTracks()[0]')
            page.locator('#answer').fill('尚未停止录音');page.locator('#answer-btn').click()
            expect(page.locator('#error')).to_contain_text('先停止录音')
            page.locator('#visit-tab').click()
            assert page.evaluate('window.testTrack.readyState')=='ended','microphone must stop on navigation'
            page.set_viewport_size({'width':390,'height':844})
            page.locator('#learn-tab').click();page.screenshot(path=str(out/'learning-mobile.png'),full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'mobile overflow'
            assert not errors,errors
            print('PASS browser: learning, visit, reload, custom context, injection, failure retry, correction, history, microphone lifecycle, mobile')
            (out/'browser.json').write_text(json.dumps({'passed':True,'model':'explicit_test_double','journeys':['learning','visit','reload','custom_context','injection','retry','correction','history','microphone_lifecycle_simulated_device','mobile'],'console_errors':errors},ensure_ascii=False,indent=2))
            browser.close()
    finally:
        server.shutdown();server.server_close()
