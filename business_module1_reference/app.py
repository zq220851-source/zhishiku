#!/usr/bin/env python3
"""Local-only module 1. Start with .venv/bin/python app.py --port 8791."""
import argparse, json, os, secrets, sys, mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlparse, unquote, parse_qs
from knowledge import ROOT, LESSONS, VISITS
from workflow import Engine, Problem
from materials import snapshot, search_materials
from voice_runtime import VoiceService, voice_config

sys.path.insert(0, str(ROOT / 'reference/coach/voice-demo'))
from remote_provider import RemoteDoctorProvider, set_credits_runtime_key, RemoteAPIError


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # Do not log answers, keys, query strings or model payloads.

    def json(self, data, status=200):
        raw = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(raw)))
        if getattr(self, 'new_owner', None):
            self.send_header('Set-Cookie', f'medrep_owner={self.new_owner}; Path=/; HttpOnly; SameSite=Strict')
        self.end_headers()
        self.wfile.write(raw)

    def identity(self):
        cookies = SimpleCookie()
        try:
            cookies.load(self.headers.get('Cookie', ''))
        except Exception:
            pass
        owner = cookies.get('medrep_owner')
        value = owner.value if owner else ''
        if len(value) != 43 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in value):
            value = secrets.token_urlsafe(32)
            self.new_owner = value
        return value

    def origin_check(self, mutate=False):
        expected = f'127.0.0.1:{self.server.server_port}'
        if self.headers.get('Host') != expected:
            raise Problem('请使用本机 127.0.0.1 地址', 403)
        if mutate and self.headers.get('Origin') != f'http://{expected}':
            raise Problem('请从本机页面操作', 403)

    def do_GET(self):
        try:
            self.origin_check()
            owner = self.identity()
            path = urlparse(self.path).path
            if path == '/api/config':
                return self.json({'lessons': [{k:v for k,v in d.items() if k not in ('checks','practice')} for d in LESSONS.values()],
                                  'visits': [{'id':v['id'], 'title':v['title']} for v in VISITS.values()],
                                  'model': self.server.provider.readiness(), 'test_mode': self.server.test_mode})
            if path.startswith('/api/courses/'):
                try:
                    return self.json(snapshot(unquote(path.split('/')[-1])))
                except ValueError as e:
                    raise Problem(str(e), 404)
            if path == '/api/voice/config':
                return self.json(voice_config(self.server.provider))
            if path == '/api/history':
                return self.json({'runs': self.server.engine.listing(owner), 'evidence': self.server.engine.history(owner)})
            if path.startswith('/api/runs/'):
                return self.json(self.server.engine.view(self.server.engine.load('runs', path.split('/')[-1], owner)))
            if path.startswith('/api/sheets/'):
                return self.json(self.server.engine.load('sheets', path.split('/')[-1], owner))
            assets = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css', '/materials.js': 'materials.js', '/voice.js': 'voice.js', '/livekit-client.js': 'vendor/livekit-client.js'}
            if path not in assets:
                raise Problem('页面不存在', 404)
            file = ROOT / 'web' / assets[path]
            raw = file.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', mimetypes.guess_type(file)[0] + '; charset=utf-8')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self' ws://127.0.0.1:7880 http://127.0.0.1:7880; media-src 'self' blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.send_header('Content-Length', str(len(raw)))
            if getattr(self, 'new_owner', None):
                self.send_header('Set-Cookie', f'medrep_owner={self.new_owner}; Path=/; HttpOnly; SameSite=Strict')
            self.end_headers()
            self.wfile.write(raw)
        except Problem as e:
            self.json({'error':str(e)}, e.status)

    def do_POST(self):
        try:
            self.origin_check(mutate=True)
            owner = self.identity()
            if 'application/json' not in self.headers.get('Content-Type', ''):
                raise Problem('需要 JSON 请求', 415)
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 6_100_000:
                raise Problem('请求过大或为空', 413)
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise Problem('请求必须是对象')
            path = urlparse(self.path).path
            engine = self.server.engine
            if path == '/api/credentials':
                key = body.get('key', '')
                if not isinstance(key, str) or not key.startswith('sk-') or not 12 <= len(key) <= 256:
                    raise Problem('请输入有效 API Key')
                provider = RemoteDoctorProvider(key_override=key)
                provider.chat('连接检查，只回复OK。', 'OK', max_tokens=30, fast=True)
                set_credits_runtime_key(key)
                self.server.provider = RemoteDoctorProvider()
                self.server.engine.provider = self.server.provider
                return self.json({'ready': True})
            if path == '/api/materials/search':
                return self.json({'blocks':search_materials(body.get('lesson_id'),body.get('query'),body.get('limit',5)), 'retrieval':'haystack-bm25'})
            if path == '/api/prepare':
                return self.json(engine.prepare(body.get('visit_id', ''), owner, body.get('context')))
            if path == '/api/runs':
                return self.json(engine.create(body, owner), 201)
            parts = path.split('/')
            if len(parts) == 5 and parts[1:3] == ['api', 'runs']:
                key, action = parts[3], parts[4]
                if action == 'voice':
                    return self.json(self.server.voice.start(key, owner))
                if action == 'finish':
                    return self.json(engine.finish(key, owner))
                if action == 'answer':
                    return self.json(engine.answer(key, body, owner))
                if action == 'support':
                    return self.json(engine.support(key, owner))
                if action == 'retry':
                    return self.json(engine.retry(key, owner))
                if action == 'correct':
                    return self.json(engine.correct(key, body, owner))
            if path in ('/api/audio/transcribe', '/api/audio/speak'):
                run = engine.load('runs', body.get('run_id', ''), owner)
                if path.endswith('transcribe'):
                    if run['state'] not in ('active', 'retryable'):
                        raise Problem('本轮已结束', 409)
                    from asr_provider import transcribe
                    text = transcribe(body.get('audio', ''), engine='auto')
                    return self.json({'text': text, 'submitted': False})
                idx = body.get('message_index')
                if type(idx) is not int or not 0 <= idx < len(run['transcript']) or run['transcript'][idx]['role'] != '医生':
                    raise Problem('只能朗读本轮医生发言')
                from tts_provider import synthesize
                raw = synthesize(run['transcript'][idx]['text'], 'Andre')
                self.send_response(200)
                self.send_header('Content-Type', 'audio/wav')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
            raise Problem('接口不存在', 404)
        except Problem as e:
            self.json({'error': str(e)}, e.status)
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            self.json({'error': '输入格式不正确：' + str(e)[:100]}, 400)
        except Exception:
            self.json({'error': '服务暂时不可用，内容不会被自动改写；请稍后重试。'}, 503)


def make_server(port, db, provider=None, test_mode=False):
    provider = provider or RemoteDoctorProvider()
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    server.provider, server.test_mode = provider, test_mode
    server.engine = Engine(db, provider)
    server.voice = VoiceService(server.engine)
    return server


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8791)
    parser.add_argument('--db', default=str(ROOT / 'runtime/module1.sqlite'))
    args = parser.parse_args()
    server = make_server(args.port, args.db)
    print(f'MedRep 第一模块 http://127.0.0.1:{server.server_port}', flush=True)
    server.serve_forever()
