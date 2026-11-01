"""Start an isolated local stack. Uses .env.local; never embeds provider secrets."""
import argparse
import json
import os
from pathlib import Path
import secrets
import signal
import ssl
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1]

def environment():
    env=dict(os.environ)
    # python.org macOS installs may lack their default CA bundle. Preserve TLS
    # verification by using the system trust bundle, never an unverified context.
    if not ssl.get_default_verify_paths().cafile and Path('/etc/ssl/cert.pem').is_file():
        env.setdefault('SSL_CERT_FILE','/etc/ssl/cert.pem')
    path=ROOT/'.env.local'
    if path.exists():
        for line in path.read_text().splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                k,v=line.split('=',1);env.setdefault(k.strip(),v.strip().strip('"').strip("'"))
    runtime=ROOT/'runtime';runtime.mkdir(exist_ok=True,mode=0o700)
    secret_file=runtime/'bridge-secrets.json'
    if not secret_file.exists():
        secret_file.write_text(json.dumps({'owner':secrets.token_urlsafe(48),'review':secrets.token_urlsafe(48)}));secret_file.chmod(0o600)
    private=json.loads(secret_file.read_text())
    env.update({'DATABASE_URL':'sqlite:///'+str(runtime/'platform.sqlite'),'APP_PUBLIC_ORIGIN':'http://localhost:5190',
        'PLATFORM_TENANT_ID':'local-medrep','COOKIE_SECURE':'false','MOBILE_ALLOWED_ORIGINS':'http://localhost:5190,http://127.0.0.1:5190',
        'MEDREP_MODULE1_READONLY_ORIGIN':'http://127.0.0.1:8791','MEDREP_MODULE1_COACH_ORIGIN':'http://127.0.0.1:8791',
        'MEDREP_MODULE1_OWNER_SECRET':private['owner'],'MEDREP_MODULE2_BRIDGE_SECRET':private['review'],
        'MEDREP_MODULE2_ORIGIN':'http://127.0.0.1:3402','MEDREP_DAILY_WORKSPACE_ORIGIN':'http://127.0.0.1:8887',
        'MEDREP_DAILY_READONLY_ORIGIN':'http://127.0.0.1:8887','MODULE1_BASE_URL':'http://127.0.0.1:8791',
        'WATCHPACK_POLLING':'true','MODULE2_LIVE_MODE':'true',
        'MODULE2_LIVE_DATABASE_PATH':str(runtime/'review.sqlite'),'MODULE2_DATABASE_PATH':str(runtime/'review-test.sqlite'),
        'MODULE2_MODEL_API_KEY':env.get('OPENAI_NEXT_API_KEY',''),'MODULE2_MODEL_BASE_URL':env.get('MEDREP_CHAT_API_URL','https://api.openai-next.com/v1/chat/completions').removesuffix('/chat/completions'),
        'MODULE2_MODEL_NAME':env.get('MEDREP_CHAT_MODEL','deepseek-v4-pro'),'MODULE2_MODEL_DATA_AUTHORIZED':'true','MODULE2_KNOWLEDGE_DATA_AUTHORIZED':'true',
        'VITE_PLATFORM_API_URL':'http://localhost:5190','HAYSTACK_TELEMETRY_ENABLED':'false'})
    # Runtime credentials remain server-side. Old LiveKit gateway is not used.
    env.pop('LIVEKIT_URL',None)
    env.setdefault('LLM_API_KEY',env.get('OPENAI_NEXT_API_KEY',''))
    env.setdefault('LLM_API_URL',env.get('MEDREP_CHAT_API_URL',''))
    env.setdefault('LLM_MODEL',env.get('MEDREP_CHAT_MODEL',''))
    return env

def main():
    env=environment();backend=ROOT/'backend';py=str(backend/'.venv/bin/python')
    business_py=env.get('MEDREP_BUSINESS_PYTHON',str(ROOT/'business_module1_reference/.venv/bin/python'))
    if not Path(business_py).exists():raise SystemExit('请先安装模块一 requirements.txt，或设置 MEDREP_BUSINESS_PYTHON')
    subprocess.run([py,'-m','alembic','upgrade','head'],cwd=backend,env=env,check=True)
    account=ROOT/'runtime/local-account.json'
    if not account.exists():
        password=secrets.token_urlsafe(18)
        code="from platform_core.config import load_settings;from platform_core.db import engine_for;from scripts.provision_mobile_user import provision;import os;s=load_settings();provision(engine_for(s.database_url),s.tenant_id,'medrep','体验用户','employee',os.environ['LOCAL_BOOTSTRAP_PASSWORD'])"
        subprocess.run([py,'-c',code],cwd=backend,env={**env,'LOCAL_BOOTSTRAP_PASSWORD':password},check=True)
        account.write_text(json.dumps({'username':'medrep','password':password},ensure_ascii=False));account.chmod(0o600)
        note=ROOT/'本机体验说明.txt';note.write_text('体验地址：http://localhost:5190/\n账号：medrep\n临时密码：'+password+'\n仅用于本机验证；外部语音服务权限以实际连接结果为准。\n');note.chmod(0o600)
    if not (ROOT/'business_module2_reference/.next/BUILD_ID').exists() or any(
        p.stat().st_mtime>(ROOT/'business_module2_reference/.next/BUILD_ID').stat().st_mtime
        for folder in ('app','lib') for p in (ROOT/'business_module2_reference'/folder).rglob('*') if p.is_file()):
        subprocess.run(['npm','run','build'],cwd=ROOT/'business_module2_reference',env=env,check=True)
    subprocess.run(['npm','run','build'],cwd=ROOT/'mobile_app',env=env,check=True)
    jobs=[([business_py,'-m','uvicorn','asgi:create_app','--factory','--host','127.0.0.1','--port','8791'],ROOT/'business_module1_reference','module1'),
          (['./node_modules/.bin/next','start','--hostname','127.0.0.1','--port','3402'],ROOT/'business_module2_reference','module2'),
          (['node','scripts/dev.mjs'],ROOT/'business_module3_reference','module3'),
          ([py,'-m','uvicorn','platform_core.server:app','--host','127.0.0.1','--port','9011','--no-access-log'],backend,'platform'),
          (['npm','run','preview','--','--host','localhost','--port','5190','--strictPort'],ROOT/'mobile_app','h5')]
    children=[];files=[]
    try:
        for command,cwd,name in jobs:
            if name=='module3':subprocess.run(['node','scripts/bundle.mjs'],cwd=cwd,env=env,check=True)
            log=(ROOT/'runtime'/f'{name}.log').open('ab');files.append(log)
            jobenv={**env,'PORT':'8887'} if name=='module3' else env
            p=subprocess.Popen(command,cwd=cwd,env=jobenv,stdout=log,stderr=log);children.append(p)
        print('本机体验：http://localhost:5190/；登录信息见 本机体验说明.txt',flush=True)
        while True:
            time.sleep(1)
            for i,p in enumerate(children):
                if p.poll() is not None:raise RuntimeError(jobs[i][2]+' 已退出，见 runtime 日志')
    except KeyboardInterrupt:pass
    finally:
        for p in children:
            if p.poll() is None:p.terminate()
        for p in children:
            try:p.wait(timeout=8)
            except subprocess.TimeoutExpired:p.kill()
        for f in files:f.close()
if __name__=='__main__':main()
