from pathlib import Path

def test_mobile_routes_public_but_internal_routes_rejected():
    caddy=(Path(__file__).resolve().parents[1]/'deploy/Caddyfile.staging').read_text()
    assert '/v1/mobile/*' in caddy
    assert 'respond @internal 404' in caddy
    assert 'respond @other_api 404' in caddy
