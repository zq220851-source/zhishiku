import unittest,tempfile,threading,json,urllib.request,urllib.error,http.cookiejar,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import make_server
from doubles import ScriptedProvider,FIXTURES as F


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.server=make_server(0,Path(self.tmp.name)/'state.db',ScriptedProvider(),True)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.base=f'http://127.0.0.1:{self.server.server_port}'
        self.client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def tearDown(self):self.server.shutdown();self.server.server_close();self.tmp.cleanup()
    def request(self,path,body=None,origin=True,client=None):
        headers={'Content-Type':'application/json'}
        if origin:headers['Origin']=self.base
        req=urllib.request.Request(self.base+path,data=None if body is None else json.dumps(body).encode(),headers=headers)
        try:
            with (client or self.client).open(req) as r:return r.status,json.load(r)
        except urllib.error.HTTPError as e:return e.code,json.load(e)
    def test_two_http_journeys(self):
        status,cfg=self.request('/api/config');self.assertEqual(status,200);self.assertTrue(cfg['test_mode'])
        status,r=self.request('/api/runs',{'mode':'learn','lesson_id':'demo-evidence'});self.assertEqual(status,201)
        _,r=self.request('/api/runs/'+r['id']+'/answer',{'answer':F['learning']['good'],'request_id':'http-request1','revision':r['revision']})
        self.assertEqual(r['state'],'review')
        _,s=self.request('/api/prepare',{'visit_id':'demo-visit'})
        _,r=self.request('/api/runs',{'mode':'visit','sheet_id':s['id'],'option_id':'evidence_scope'})
        _,r=self.request('/api/runs/'+r['id']+'/answer',{'answer':F['visit']['good'],'request_id':'http-request2','revision':r['revision']})
        _,s=self.request('/api/sheets/'+s['id']);self.assertEqual(len(s['practice_results']),1)
        _,h=self.request('/api/history');self.assertEqual(len(h['runs']),2)
    def test_cross_browser_and_cross_site_rejected(self):
        _,r=self.request('/api/runs',{'mode':'learn','lesson_id':'demo-evidence'})
        client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.assertEqual(self.request('/api/runs/'+r['id'],client=client)[0],404)
        self.assertEqual(self.request('/api/runs',{'mode':'learn','lesson_id':'demo-evidence'},origin=False)[0],403)
    def test_bad_requests(self):
        self.assertEqual(self.request('/api/prepare',{'visit_id':'missing'})[0],400)
        self.assertEqual(self.request('/api/runs',{'mode':'learn','lesson_id':'missing'})[0],400)
        self.assertEqual(self.request('/api/audio/speak',{'run_id':'missing','message_index':0})[0],404)
        self.assertEqual(self.request('/api/unknown',{})[0],404)

if __name__=='__main__':unittest.main()
