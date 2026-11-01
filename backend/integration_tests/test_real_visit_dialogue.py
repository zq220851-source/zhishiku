"""Real localhost Module 1 rehearsal with scripted (NOT production) model."""
from test_real_module1 import module1, gettoken
from tests.conftest import client, environment


def test_previsit_forecast_then_visit_dialogue(client, environment, module1):
    alice=gettoken(client,environment,'visit_dialog_alice')
    bob=gettoken(client,environment,'visit_dialog_bob')
    prepare=client.post('/v1/mobile/coach/prepare',headers=alice,json={
        'doctor':'匿名科室医生','goal':'围绕研究适用边界沟通',
        'facts':'已知：本次沟通会涉及原始研究材料',
        'lesson_id':'visit-communication',
    })
    assert prepare.status_code==200,prepare.text
    sheet=prepare.json()
    assert sheet.get('material',{}).get('blocks')
    option=sheet['priorities'][0]['id']
    sheet_id=sheet['id']
    frozen=client.post(f'/v1/mobile/coach/sheets/{sheet_id}/freeze',headers=alice,
        json={'selected_ids':[option],'previsit_confirmed':True})
    assert frozen.status_code==200, frozen.text
    assert frozen.json()['forecast']['status']=='FROZEN'
    practice=client.post('/v1/mobile/coach/runs/visit',headers=alice,
        json={'sheet_id':sheet_id,'option_id':option})
    assert practice.status_code==201,practice.text
    run=practice.json();id=run['id']
    assert run['mode']=='visit' and run['sheet_id']==sheet_id
    assert run['transcript'][0]['role']=='医生'
    assert client.get(f'/v1/mobile/coach/runs/{id}',headers=bob).status_code==404
    response=client.post(f'/v1/mobile/coach/runs/{id}/answer',headers=alice,json={
        'answer':'我先听您的具体疑问，只依据当前材料的研究人群和终点交流，其他信息会回去核对。',
        'revision':run['revision'],'request_id':'visit-dialogue-request-001'
    })
    assert response.status_code==200,response.text
    ongoing=response.json()
    assert ongoing['mode']=='visit'
    assert any(x['role']=='药代' for x in ongoing['transcript'])
    support=client.post(f'/v1/mobile/coach/runs/{id}/support',headers=alice,json={})
    assert support.status_code==200,support.text
    assert support.json().get('material') or support.json().get('sections')
    assert client.post(f'/v1/mobile/coach/runs/{id}/support',headers=bob,json={}).status_code==404
    finished=client.post(f'/v1/mobile/coach/runs/{id}/finish',headers=alice,json={})
    assert finished.status_code==200,finished.text
    completed=finished.json()
    assert completed['state']=='review' and completed['review'] is not None
    retried=client.post(f'/v1/mobile/coach/runs/{id}/retry',headers=alice,json={})
    assert retried.status_code==200,retried.text
    assert retried.json()['state']=='active' and retried.json()['attempt']==2
    assert client.post(f'/v1/mobile/coach/runs/{id}/retry',headers=bob,json={}).status_code==404
