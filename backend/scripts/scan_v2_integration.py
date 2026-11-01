"""Read-only V2 integration risk inventory. Usage:
 python scripts/scan_v2_integration.py /path/to/MedRep_Coach_三模块运行时联动_V2

This is a heuristic scan, not a security audit. Returns status 0 even when findings exist.
"""
import argparse
from pathlib import Path

checks = [
 ('模块一 localhost 网关仍在', 'module1_source/asgi.py', "request.url.hostname!='127.0.0.1'"),
 ('模块一测试 owner Cookie', 'module1_source/asgi.py', "request.cookies.get('medrep_owner'"),
 ('模块一运行时 API Key 输入接口', 'module1_source/asgi.py', "@app.post('/api/credentials')"),
 ('主演练台创建会话未绑定用户', 'medrep_coach_with_ai_rules/app/api/sessions/route.ts', 'createSession(scenario.id, scenario.openingLine)'),
 ('主演练台查询会话仅以 ID 定位', 'medrep_coach_with_ai_rules/app/api/sessions/[id]/route.ts', 'getSession(id)'),
 ('模块二测试角色 Cookie', 'medrep_coach_with_ai_rules/module2/lib/http.ts', "module2_test_session"),
 ('模块二 localhost 网关仍在', 'medrep_coach_with_ai_rules/module2/lib/http.ts', "LOCAL_ONLY"),
]


def main():
    parser=argparse.ArgumentParser(description='Read-only V2 integration scan')
    parser.add_argument('source', type=Path)
    args=parser.parse_args()
    root=args.source
    for label, relative, needle in checks:
        path=root / relative
        if not path.is_file():
            print(f'[未知] {label}: 路径不存在：{relative}')
        elif needle in path.read_text(encoding='utf-8'):
            print(f'[需对接] {label}: {relative}')
        else:
            print(f'[待人工复查] {label}: 预期代码片段已变化：{relative}')
    print('说明：脚本不修改源代码，不等于完整安全审计。')


if __name__ == '__main__':
    main()
