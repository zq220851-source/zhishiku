"""Authenticated, opt-in, read-only module 3 live digest adapter.

Public industry news ONLY. Not an employee profile, personalized push, medical
review, raw scholar search, private product assignment or legacy cookie proxy.
No user-controlled upstream URL or query parameters are accepted.
"""
import ipaddress
import json
import os
from urllib.parse import urlsplit

import httpx
from fastapi import Depends, HTTPException

MAX_BYTES = 1_500_000
MAX_ITEMS = 6


def daily_origin():
    raw = os.environ.get('MEDREP_DAILY_READONLY_ORIGIN', '').strip().rstrip('/')
    if not raw or len(raw) > 256:
        raise HTTPException(503, '学术日报尚未连接')
    try:
        url = urlsplit(raw)
        host = (url.hostname or '').lower()
        port = url.port
        if url.username or url.password or url.path or url.query or url.fragment:
            raise ValueError('tainted origin')
        if url.scheme == 'http':
            if host != '127.0.0.1' or port != 8787:
                raise ValueError('local dev origin only')
        elif url.scheme == 'https':
            if port not in (None, 443) or '.' not in host or host.endswith('.'):
                raise ValueError('invalid HTTPS host')
            # Deny literal IPs and non-routable hostnames; configured DNS is
            # trusted infrastructure and must be egress-restricted at deployment.
            try:
                ipaddress.ip_address(host)
            except ValueError:
                pass
            else:
                raise ValueError('literal IP')
            if host == 'localhost' or host.endswith(('.localhost', '.local', '.internal')):
                raise ValueError('local address')
        else:
            raise ValueError('HTTPS required')
    except ValueError:
        raise HTTPException(503, '学术日报内部源配置无效')
    return raw


def fetch_daily():
    origin = daily_origin()
    try:
        with httpx.Client(timeout=httpx.Timeout(20.0), follow_redirects=False, trust_env=False) as client:
            with client.stream('GET', origin + '/api/digest?mode=live&length=brief',
                headers={'Accept': 'application/json'}) as response:
                if response.status_code != 200:
                    raise HTTPException(503, '日报源暂不可用')
                if 'application/json' not in response.headers.get('content-type', '').lower():
                    raise HTTPException(502, '日报源不是 JSON')
                chunks, total = [], 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > MAX_BYTES:
                        raise HTTPException(502, '日报源响应超出限制')
                    chunks.append(chunk)
        data = json.loads(b''.join(chunks))
        if not isinstance(data, dict):
            raise ValueError('invalid shape')
        return data
    except HTTPException:
        raise
    except (httpx.HTTPError, json.JSONDecodeError, ValueError):
        raise HTTPException(503, '日报源连接或响应异常')


def safe_str(value, max_len=300):
    return value[:max_len] if isinstance(value, str) else ''


def safe_url(value):
    if not isinstance(value, str) or len(value) > 1500:
        return None
    try:
        url = urlsplit(value)
        if url.scheme != 'https' or not url.hostname or url.username or url.password:
            return None
        host = url.hostname.lower()
        if host == 'localhost' or host.endswith(('.localhost','.local','.internal')):
            return None
        try:
            ipaddress.ip_address(host)
            return None
        except ValueError:
            pass
        return value
    except ValueError:
        return None


def present_digest(data):
    if data.get('mode') != 'live' or data.get('status') not in ('ok','partial'):
        raise HTTPException(503, '实时日报尚未生成，不展示演示或失败数据')
    if data.get('stale') is True:
        raise HTTPException(503, '日报数据已过期，请等待更新')
    industry = data.get('industry')
    if not isinstance(industry, list):
        raise HTTPException(503, '日报源数据格式不兼容')
    selected = []
    for item in industry[:40]:
        if not isinstance(item, dict):
            continue
        link = safe_url(item.get('url'))
        title = safe_str(item.get('title'), 240)
        if not link or not title:
            continue
        selected.append({
            'id': safe_str(item.get('id'), 200),
            'title': title,
            'source': safe_str(item.get('source'), 130),
            'published_at': safe_str(item.get('publishedAt'), 40),
            'kind': safe_str(item.get('kind'), 80),
            'summary': safe_str(item.get('summary'), 700),
            'limitations': safe_str(item.get('limitations'), 500),
            'review_status': safe_str(item.get('reviewStatus'), 60) or 'not_reviewed',
            'url': link,
        })
        if len(selected) >= MAX_ITEMS:
            break
    return {
        'source': 'MODULE3', 'mode': 'live',
        'status': data['status'],
        'date': safe_str(data.get('date'), 40),
        'generated_at': safe_str(data.get('generatedAt'), 64),
        'items': selected,
        'notice': '仅展示实时来源的行业动态及原始链接；摘要未经企业医学审核，不作为临床、推广或用药建议。',
    }


def attach_daily_routes(app, actor):
    @app.get('/v1/mobile/daily/industry')
    def industry_digest(_user=Depends(actor)):
        return present_digest(fetch_daily())
