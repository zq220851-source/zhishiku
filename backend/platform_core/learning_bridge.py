"""Opt-in, authenticated READ-ONLY adapter for Module 1 source lessons.

NOT a bridge for per-employee sessions, freeze/prepare, voice, or module 2.
Only usable when Module 1 runs on the same network namespace at 127.0.0.1.
Never forwards browser cookies or accepts arbitrary upstream URLs.
"""
import json
import os
import re
from urllib.parse import urlsplit
import httpx
from fastapi import Depends, HTTPException

LESSON_ID = re.compile(r'^[A-Za-z0-9_.-]{1,80}$')
MAX_RESPONSE = 1_000_000


def internal_origin():
    value = os.environ.get('MEDREP_MODULE1_READONLY_ORIGIN', '').strip().rstrip('/')
    if not value:
        raise HTTPException(503, '课程服务尚未连接。需部署模块一并启用内部只读连接。')
    parsed = urlsplit(value)
    if (parsed.scheme != 'http' or parsed.hostname != '127.0.0.1'
            or parsed.port not in (8791, 8892) or parsed.username or parsed.password
            or parsed.path or parsed.query or parsed.fragment):
        raise HTTPException(503, '课程内部连接配置无效；仅允许同机回环地址。')
    return value


def fetch_module1(path):
    origin = internal_origin()
    try:
        with httpx.Client(timeout=httpx.Timeout(6.0), follow_redirects=False, trust_env=False) as client:
            with client.stream('GET', origin + path, headers={'Accept': 'application/json'}) as response:
                if response.status_code == 404:
                    raise HTTPException(404, '课程不存在')
                if response.status_code != 200:
                    raise HTTPException(503, '课程上游暂时不可用')
                parts=[]; size=0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_RESPONSE:
                        raise HTTPException(502, '课程响应超出大小限制')
                    parts.append(chunk)
                body = json.loads(b''.join(parts))
                if not isinstance(body, dict):
                    raise ValueError('not JSON object')
                return body
    except HTTPException:
        raise
    except (httpx.RequestError, ValueError, json.JSONDecodeError):
        raise HTTPException(503, '课程服务连接或响应异常')


def attach_learning_routes(app, actor):
    @app.get('/v1/mobile/learning/catalog')
    def catalog(_user=Depends(actor)):
        data = fetch_module1('/api/config')
        lessons = data.get('lessons')
        if not isinstance(lessons, list):
            raise HTTPException(503, '课程目录数据结构不兼容')
        cleaned=[]
        for item in lessons:
            if isinstance(item, dict) and isinstance(item.get('id'), str) and isinstance(item.get('title'), str):
                cleaned.append({k:item.get(k) for k in ('id','title','kind','status','duration')})
        return {'source':'MODULE1', 'lessons':cleaned, 'notice':'课程来自模块一现有知识库；保留源材料审核状态，不代表医学审核通过。'}

    @app.get('/v1/mobile/learning/courses/{lesson_id}')
    def course(lesson_id: str, _user=Depends(actor)):
        if not LESSON_ID.fullmatch(lesson_id):
            raise HTTPException(404, '无效的课程 ID')
        data = fetch_module1('/api/courses/' + lesson_id)
        if data.get('lesson_id') not in (None, lesson_id):
            raise HTTPException(503, '课程来源标识不一致')
        return {**data, 'source':'MODULE1', 'lesson_id':lesson_id,
                'block_count':len(data.get('blocks',[])), 'reference_count':len(data.get('references',[]))}

    @app.get('/v1/mobile/learning/search')
    def search(lesson_id:str,q:str,_user=Depends(actor)):
        if not LESSON_ID.fullmatch(lesson_id) or not 1 <= len(q) <= 300:
            raise HTTPException(422,'课程或检索内容无效')
        from urllib.parse import urlencode
        return fetch_module1('/api/knowledge/search?'+urlencode({'lessonId':lesson_id,'q':q}))
