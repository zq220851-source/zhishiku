"""Install the isolated local stack using the checked-in dependency manifests."""
import subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if sys.version_info<(3,11):raise SystemExit('需要 Python 3.11 或更新版本')
def run(args,cwd=ROOT):subprocess.run(args,cwd=cwd,check=True)
for name in ('backend','business_module1_reference'):
    cwd=ROOT/name
    run([sys.executable,'-m','venv',str(cwd/'.venv')])
    args=[str(cwd/'.venv/bin/python'),'-m','pip','install','-r','requirements.txt']
    if name=='backend':args+=['-r','requirements-test.txt']
    run(args,cwd)
for name in ('mobile_app','business_module2_reference'):
    run(['npm','ci','--no-audit','--no-fund'],ROOT/name)
run(['npm','run','build'],ROOT/'business_module2_reference')
print('依赖已安装；运行 python3 scripts/run_local.py')
