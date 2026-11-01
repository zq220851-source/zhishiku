"""Loopback-only test HTTP wrapper around real Module1 Engine. NOT an enterprise API."""
import json, os, tempfile, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent/'tests'))
from workflow import Engine, Problem
from doubles import ScriptedProvider
from test_bridge import apply_reviewed_test_candidate, review_external_test_candidate, sheet_hash, freeze_user_selection_for_test

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def send(self, status, obj):
        body=json.dumps(obj, ensure_ascii=False).encode('utf8')
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.end_headers();self.wfile.write(body)
    def do_GET(self):
        if self.path=='/health':return self.send(200,{'status':'TEST_ONLY','module':'MODULE1'})
        self.send(404,{'error':'not found'})
    def do_POST(self):
        if self.headers.get('Content-Type')!='application/json' or int(self.headers.get('Content-Length','0'))>500000:
            return self.send(400,{'error':'json only'} )
        try:
            body=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))))
            if self.path=='/test/prepare':
                generated=self.server.engine.prepare('demo-visit', self.server.owner)
                sheet=freeze_user_selection_for_test(self.server.engine,self.server.owner,generated,body.get('selectedOptionIds',['needs','followup']))
                return self.send(200,{'sheet':sheet,'sheetHash':sheet_hash(sheet)})
            if self.path=='/test/practice':
                if body.get('answer') not in ('这次我先确认您想核对哪类人群。C-17只有A类的X，没有同期比较组，B类和Y都没有依据，所以不能说更好。没核实的我查原始资料，明天下午跟您确认，今天不把还没查的说成已经做完。',):
                    raise Problem('只允许冻结的虚构练习样例')
                run=self.server.engine.create({'mode':'visit','sheet_id':body['sheetId'],'option_id':body['optionId']},self.server.owner)
                outcome=self.server.engine.answer(run['id'],{'answer':body['answer'],
                  'request_id':'scripted-fixture-0001','revision':run['revision']},self.server.owner)
                if outcome['state']!='review':
                    outcome=self.server.engine.finish(run['id'],self.server.owner)
                return self.send(200,{'run':self.server.engine.load('runs',run['id'],self.server.owner)})
            if self.path=='/test/apply':
                result=apply_reviewed_test_candidate(self.server.engine,self.server.owner,body['sourceSheetId'],body['candidate'],body['decision'])
                return self.send(200,{'sheet':result,'receipt':result['reviewReceipt']})
            if self.path=='/test/review-external':
                return self.send(200,review_external_test_candidate(body['inbox'],body['sourceId'],body['reviewer'],body['decision'],body['evidenceHash']))
            return self.send(404,{'error':'not found'})
        except (Problem,KeyError,TypeError,ValueError) as e:
            return self.send(e.status if isinstance(e,Problem) else 400, {'error':str(e)[:150]})
        except Exception:
            return self.send(500,{'error':'test request failed'})

if __name__=='__main__':
    if os.environ.get('MEDREP_TEST_BRIDGE_ENABLED')!='1':raise SystemExit('Set MEDREP_TEST_BRIDGE_ENABLED=1 for synthetic local tests')
    port=int(os.environ.get('M1_BRIDGE_PORT','8799'))
    if not 1024<=port<=65535:raise SystemExit('invalid port')
    with tempfile.TemporaryDirectory() as td:
        server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
        server.engine=Engine(str(Path(td)/'module1_test.sqlite'),ScriptedProvider())
        server.owner='fixture-owner-only'
        print(f'M1 TEST bridge on 127.0.0.1:{port}',flush=True)
        server.serve_forever()
