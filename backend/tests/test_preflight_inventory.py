import sqlite3
from scripts.preflight import check_environment
from scripts.legacy_storage_inventory import inventory


def test_preflight_rejects_insecure_production_configuration():
    flags = check_environment({'DATABASE_URL':'sqlite:///prod.db','APP_PUBLIC_ORIGIN':'http://localhost:9010',
                               'COOKIE_SECURE':'false','POSTGRES_PASSWORD':'CHANGE_ME_TO_LONG_RANDOM_PASSWORD'})
    assert sum(not ok for _, ok, _ in flags) >= 5


def test_preflight_accepts_syntax_only_not_real_production():
    env = dict(DATABASE_URL='postgresql+psycopg://medrep_app:LongSecret_for_Staging123abc@db:5432/medrep_platform',
               APP_PUBLIC_ORIGIN='https://coach.acme.test.cn', APP_DOMAIN='coach.acme.test.cn',
               COOKIE_SECURE='true', PLATFORM_TENANT_ID='company', FEISHU_APP_ID='cli_abc',
               FEISHU_APP_SECRET='abcdefghijklmnop', POSTGRES_PASSWORD='LongSecret_for_Staging123abc',
               SESSION_TTL_SECONDS='3600')
    assert all(ok for _, ok, _ in check_environment(env))


def test_inventory_counts_not_payload(tmp_path):
    p = tmp_path/'legacy.sqlite'
    with sqlite3.connect(p) as conn:
        conn.execute('CREATE TABLE sessions (id TEXT, transcript TEXT)')
        conn.execute('INSERT INTO sessions VALUES (?,?)', ('s01','private_patient_name'))
    result = inventory(tmp_path)
    assert len(result) == 1
    assert result[0]['tables'] == [{'name':'sessions', 'rows':1}]
    assert 'private_patient_name' not in str(result)
