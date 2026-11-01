import argparse,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
parser=argparse.ArgumentParser();parser.add_argument('--config-from');parser.add_argument('--port',type=int,default=8791);args=parser.parse_args()
if args.config_from:
    from scripts.credentials import configure
    configure(args.config_from)
from asgi import create_app
import uvicorn
print(f'MedRep 第一模块 http://127.0.0.1:{args.port}',flush=True)
uvicorn.run(create_app(),host='127.0.0.1',port=args.port,log_level='warning',access_log=False)
