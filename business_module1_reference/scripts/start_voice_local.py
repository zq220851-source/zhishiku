"""Start loopback-only LiveKit with generated local credentials, then the app."""
import argparse,asyncio,json,os,secrets,subprocess,sys,time,socket
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
p=argparse.ArgumentParser();p.add_argument('--config-from');p.add_argument('--port',type=int,default=8791);args=p.parse_args()
if args.config_from:
    from scripts.credentials import configure
    configure(args.config_from)
config=ROOT/'runtime/livekit-local.json';config.parent.mkdir(exist_ok=True)
if not config.exists():
    config.write_text(json.dumps({'url':'ws://127.0.0.1:7880','key':'medrep-local','secret':secrets.token_urlsafe(40)}));config.chmod(0o600)
settings=json.loads(config.read_text())
os.environ.update(LIVEKIT_URL=settings['url'],LIVEKIT_API_KEY=settings['key'],LIVEKIT_API_SECRET=settings['secret'])
binary=ROOT/'runtime/bin/livekit-server'
if not binary.exists():raise SystemExit('缺少本地LiveKit服务程序，请按docs/IMPLEMENTATION_V2.md配置已有服务。')
# Reuse only the local service started with these exact credentials. If a
# different service occupies the port, fail visibly rather than replacing it.
try:
    with socket.create_connection(('127.0.0.1',7880),timeout=.2):running=True
except OSError:running=False
server=None
if running:
    async def verify():
        from livekit import api
        async with api.LiveKitAPI(settings['url'],settings['key'],settings['secret']) as client:
            await client.room.list_rooms(api.ListRoomsRequest())
    try:asyncio.run(verify())
    except Exception:raise SystemExit('7880端口已有其他配置的语音服务。请使用对应LIVEKIT配置启动，或先关闭该服务。')
if not running:
    keyfile=ROOT/'runtime/livekit-keys.yaml'
    keyfile.write_text(json.dumps({settings['key']:settings['secret']}));keyfile.chmod(0o600)
    log=(ROOT/'runtime/livekit-local.log').open('a')
    server=subprocess.Popen([str(binary),'--dev','--bind','127.0.0.1','--node-ip','127.0.0.1','--key-file',str(keyfile)],stdout=log,stderr=log)
    for _ in range(60):
        if server.poll() is not None:raise SystemExit('LiveKit启动失败，请查看runtime/livekit-local.log。')
        try:
            with socket.create_connection(('127.0.0.1',7880),timeout=.2):break
        except OSError:time.sleep(.1)
from asgi import create_app
import uvicorn
try:uvicorn.run(create_app(),host='127.0.0.1',port=args.port,log_level='warning',access_log=False)
finally:
    if server:server.terminate()
