"""Real FastAPI+browser journeys with explicitly scripted model responses."""
import json,socket,sys,tempfile,threading,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import uvicorn
from playwright.sync_api import sync_playwright,expect
from asgi import create_app
from tests.doubles import ScriptedProvider,FIXTURES as F
out=Path('test-results/v2');out.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory() as td:
    provider=ScriptedProvider();sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(create_app(Path(td)/'browser.db',provider,True),log_level='error',access_log=False))
    threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True).start()
    while not server.started:time.sleep(.05)
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            page=browser.new_page(viewport={'width':1280,'height':960});errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(f'http://127.0.0.1:{port}/')
            expect(page.locator('#lesson-select')).to_have_value('D-NSCLC__CE')
            expect(page.locator('#material-visual .comparison-grid section')).to_have_count(4)
            expect(page.locator('#material-analogy')).to_contain_text('待验的性能宣称')
            page.screenshot(path=str(out/'full-course-desktop.png'))
            page.locator('#search-query').fill('EGFR 状态未明');page.locator('#material-search button').click()
            expect(page.locator('#search-results')).to_contain_text('EGFR')
            page.locator('#lesson-select').select_option('D-AS')
            expect(page.locator('#material-visual .process-list li')).to_have_count(6)
            page.locator('#lesson-select').select_option('D-AD')
            expect(page.locator('#material-visual .concept-nodes section')).to_have_count(8)
            page.locator('#lesson-select').select_option('demo-evidence')
            expect(page.locator('#lesson')).to_contain_text('虚构')
            page.locator('#start-learn').click()
            expect(page.locator('#answer-form')).to_be_visible()
            page.locator('#answer').fill(F['learning']['wrong']);page.locator('#answer-btn').click()
            expect(page.locator('#transcript .bubble')).to_have_count(3)
            expect(page.locator('#feedback')).to_be_empty()
            page.locator('#finish-btn').click()
            expect(page.locator('#feedback')).to_contain_text('还有遗漏')
            page.locator('#feedback summary').first.click()
            page.locator('#feedback [data-material-ref]').first.click()
            expect(page.locator('#support')).to_be_visible()
            page.locator('#retry-btn').click()
            page.locator('#answer').fill(F['learning']['good']);page.locator('#answer-btn').click()
            expect(page.locator('#feedback')).to_contain_text('本次已体现')
            page.screenshot(path=str(out/'source-bound-feedback.png'))
            page.locator('#visit-tab').click();page.locator('#visit-select').select_option('custom')
            page.locator('#doctor').fill('A医院周医生（虚构）')
            page.locator('#goal').fill(F['visit']['custom_context']['goal'])
            page.locator('#visit-facts').fill(F['visit']['custom_context']['facts'])
            page.locator('#visit-lesson').select_option('D-NSCLC__CE');page.locator('#prepare-btn').click()
            expect(page.locator('#sheet')).to_contain_text('回应本次关切')
            expect(page.locator('#sheet')).not_to_contain_text('C-17')
            page.locator('[data-practice]').first.click()
            page.locator('#answer').fill(F['visit']['good']);page.locator('#answer-btn').click()
            expect(page.locator('#return-sheet')).to_be_visible();page.locator('#return-sheet').click()
            expect(page.locator('#sheet')).to_contain_text('试练后补充')
            page.reload();page.locator('#visit-tab').click();expect(page.locator('#sheet')).to_contain_text('试练后补充')
            page.locator('#learn-tab').click();page.set_viewport_size({'width':390,'height':844})
            expect(page.locator('#material-visual')).to_be_visible()
            page.screenshot(path=str(out/'full-course-mobile.png'))
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),'mobile overflow'
            assert not errors,errors
            (out/'browser.json').write_text(json.dumps({'passed':True,'model':'explicit_test_double','cases':['full_course','comparison','process','concept_map','chinese_retrieval','learning_task','no_interim_feedback','explicit_finish','material_anchor','retry','custom_visit','same_sheet_update','reload','mobile'],'errors':errors},ensure_ascii=False,indent=2))
            print('PASS browser V2: complete reading, three visuals, retrieval, learning, preparation, feedback anchors, mobile')
            browser.close()
    finally:server.should_exit=True
