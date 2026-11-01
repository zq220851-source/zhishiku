"""Read explicitly test-approved preparation guidance from module 2 for this browser.

No remote source/credentials accepted. Cookies are forwarded only to 127.0.0.1:3302.
Failure is fail-closed: an opt-in never silently substitutes an unapproved method.
"""
import json
from urllib.request import Request, urlopen


class MethodUnavailable(ValueError):
    pass


def approved_method_for_lesson(cookie: str, lesson_id: str):
    if not isinstance(cookie, str) or len(cookie) > 4096 or not isinstance(lesson_id, str):
        raise MethodUnavailable('方法授权上下文无效')
    try:
        request = Request('http://127.0.0.1:3302/api/live/methods?active=1', headers={'Cookie': cookie})
        with urlopen(request, timeout=5) as response:
            content = json.load(response)
    except Exception as exc:
        raise MethodUnavailable('模块二的获准方法无法读取，本次未使用方法') from exc
    data = content.get('data', {})
    if data.get('purpose') != 'TEST_ONLY' or not isinstance(data.get('methods'), list):
        raise MethodUnavailable('方法审批信息无效')
    for record in data['methods']:
        if not isinstance(record, dict) or lesson_id not in record.get('lessonIds', []):
            continue
        m = record.get('method')
        if not isinstance(m, dict) or not all(isinstance(m.get(k), str) and m[k].strip() for k in ('condition', 'action', 'reason')):
            continue
        if not isinstance(m.get('exceptions'), list) or not m['exceptions']:
            continue
        if not isinstance(record.get('version'), str):
            continue
        return {'id': record['id'], 'version': record['version'], 'lesson_ids': record['lessonIds'],
                'source_versions': record.get('sourceVersions', []),
                'condition': m['condition'], 'action': m['action'], 'reason': m['reason'], 'exceptions': m['exceptions']}
    return None
