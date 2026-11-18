import io
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from lrc_selection.app import create_app

TOKEN = 'test-only-local-token'

@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path, token=TOKEN)
    with TestClient(app) as c:
        c.headers['Authorization'] = 'Bearer ' + TOKEN
        yield c

def manifest(sid='test-service', count=4, catalog='test-catalog'):
    return {'schema_version': 1, 'id': sid, 'title': 'DATI SINTETICI — test', 'catalog_id': catalog,
            'photos': [{'id': f'u{i}:1', 'uuid': f'u{i}', 'local_id': i, 'filename': 'duplicate-name.jpg',
                        'camera': 'camera-a', 'captured_at': i, 'baseline_rating': 0,
                        'baseline_edit_time': 10.0, 'is_virtual_copy': i == 1} for i in range(count)]}

def imported(c, m=None):
    m = m or manifest()
    response = c.post('/api/imports', json=m)
    assert response.status_code == 200, response.text
    s = c.post(f"/api/services/{m['id']}/complete").json()
    return s

def detail(c, sid='test-service'):
    return c.get('/api/services/' + sid).json()

def configure(c, s, **changes):
    response = c.put(f"/api/services/{s['id']}/settings", json={'revision': s['revision'], 'settings': s['settings'] | changes})
    assert response.status_code == 200, response.text
    return response.json()

def jpeg(color):
    data = io.BytesIO()
    Image.new('RGB', (24, 16), color).save(data, 'JPEG')
    return data.getvalue()

def run(c, s):
    response = c.post(f"/api/services/{s['id']}/analyze", json={'revision': s['revision']})
    assert response.status_code == 200, response.text
    for _ in range(100):
        current = detail(c, s['id'])
        if current['job']['status'] not in ('running', 'queued'):
            return current
        time.sleep(.01)
    pytest.fail('Analysis did not complete')

def test_auth_host_origin_and_cookie(client):
    assert client.get('/api/services', headers={'Authorization': ''}).status_code == 401
    assert client.get('/api/services', headers={'Host': 'evil.test'}).status_code == 400
    assert client.post('/api/session', json={'token': TOKEN}, headers={'Origin': 'https://evil.test'}).status_code == 403
    assert client.post('/api/session', json={'token': TOKEN}).status_code == 200
    assert client.get('/api/services', headers={'Authorization': ''}).status_code == 200
    assert client.cookies.get('lrc_session') == TOKEN

def test_identity_idempotency_and_manifest_conflict(client):
    m = manifest()
    s = imported(client, m)
    assert len(s['photos']) == 4
    assert client.post('/api/imports', json=m).json()['revision'] == s['revision']
    changed = dict(m, title='changed')
    assert client.post('/api/imports', json=changed).status_code == 409
    other = imported(client, manifest('other', catalog='other-catalog'))
    assert other['catalog_id'] != s['catalog_id']
    m['photos'][1]['id'] = m['photos'][0]['id']
    assert client.post('/api/imports', json=m).status_code == 422

def test_safe_preview_paths_and_validation(client, tmp_path):
    m = manifest()
    m['photos'][0]['filename'] = '../../../../original.jpg'
    client.post('/api/imports', json=m)
    endpoint = '/api/services/test-service/photos/u0:1/preview'
    assert client.put(endpoint, content=b'bad').status_code == 422
    assert client.put(endpoint, content=jpeg('red')).status_code == 200
    assert client.get(endpoint).content == jpeg('red')
    assert client.put('/api/services/test-service/photos/not-present/preview', content=jpeg('red')).status_code == 404
    client.post('/api/services/test-service/complete')
    assert client.put(endpoint, content=jpeg('red')).status_code == 200
    assert client.put(endpoint, content=jpeg('blue')).status_code == 409
    assert not (tmp_path / 'original.jpg').exists()

def test_target_and_conservative_groups(client):
    m = manifest()
    client.post('/api/imports', json=m)
    for i, color in enumerate(['red', 'red', 'red', 'blue']):
        assert client.put(f'/api/services/test-service/photos/u{i}:1/preview', content=jpeg(color)).status_code == 200
    s = client.post('/api/services/test-service/complete').json()
    s = configure(client, s, target=3)
    s = run(client, s)
    assert len(s['selected_ids']) == 3
    assert 'u3:1' in s['selected_ids'] # unique image retained even when target low
    groups = s['proposal']['groups']
    assert len(groups) == 2
    assert all(set(g['members']) & set(s['selected_ids']) for g in groups)
    s = configure(client, s, target=1)
    s = run(client, s)
    assert len(s['selected_ids']) == 2 # coverage exceeds requested quantity

def test_missing_previews_never_equivalent(client):
    s = configure(client, imported(client), target=1)
    s = run(client, s)
    assert len(s['selected_ids']) == 4
    assert len(s['proposal']['groups']) == 4

def test_manual_decisions_lock_and_coverage_confirmation(client):
    s = imported(client)
    body = {'revision': s['revision'], 'state': 'excluded', 'locked': True}
    endpoint = '/api/services/test-service/decisions/u0:1'
    response = client.patch(endpoint, json=body)
    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'last_candidate'
    s = client.patch(endpoint, json=body | {'confirm_last': True}).json()
    assert client.patch(endpoint, json=body | {'confirm_last': True}).status_code == 409
    s = run(client, s)
    assert s['decisions']['u0:1'] == {'state': 'excluded', 'locked': True}
    assert 'u0:1' not in s['selected_ids']
    assert len(s['selected_ids']) == 3
    assert any('non raggiungibile' in w for w in s['proposal']['warnings'])

def test_preset_snapshot_and_unsupported_instructions(client):
    s = imported(client)
    old = s['settings']['preset_snapshot']
    r = client.put('/api/presets/wedding', json={'name': 'Changed', 'criteria': ['different'], 'version': 1})
    assert r.status_code == 200
    s = configure(client, s, instructions='Scegli solo foto con lo zio')
    assert s['settings']['preset_snapshot'] == old
    assert s['criteria'][-1]['status'] == 'unsupported'
    assert client.put('/api/presets/wedding', json={'name': 'stale', 'criteria': [], 'version': 1}).status_code == 409
    s = configure(client, s, preset_version=2)
    assert s['settings']['preset_snapshot']['name'] == 'Changed'

def test_rating_plan_preserves_existing_and_missing_edit_time(client):
    m = manifest()
    m['photos'][1]['baseline_rating'] = 5
    m['photos'][2]['baseline_rating'] = 1
    m['photos'][3]['baseline_edit_time'] = None
    s = imported(client, m)
    p = client.post('/api/services/test-service/rating-plan', json={'revision': s['revision']}).json()
    assert [i['photo_id'] for i in p['items']] == ['u0:1']
    assert p['items'][0]['target_rating'] == 1
    assert p['warnings']
    assert client.post('/api/services/test-service/rating-plan/claim', json={'batch_id': p['batch_id']}).status_code == 200
    receipt = {'batch_id': p['batch_id'], 'results': [{'photo_id': 'u0:1', 'status': 'applied', 'before': 0, 'after': 1, 'reason': ''}]}
    assert client.post('/api/services/test-service/rating-receipts', json=receipt).status_code == 200
    assert client.post('/api/services/test-service/rating-receipts', json=receipt).status_code == 200
    assert client.get('/api/services/test-service/rating-plan/latest').status_code == 409
    s = detail(client)
    assert client.post('/api/services/test-service/rating-plan', json={'revision': s['revision']}).json()['items'] == []

def test_stale_plan_and_receipt_validation(client):
    s = imported(client)
    p = client.post('/api/services/test-service/rating-plan', json={'revision': s['revision']}).json()
    s = configure(client, s, target=2)
    assert client.get('/api/services/test-service/rating-plan/latest').status_code == 409
    invalid = {'batch_id': p['batch_id'], 'results': [{'photo_id': 'foreign-photo', 'status': 'applied', 'after': 1}]}
    assert client.post('/api/services/test-service/rating-receipts', json=invalid).status_code == 422
    # A stale plan cannot be claimed after edits.
    assert client.post('/api/services/test-service/rating-plan/claim', json={'batch_id': p['batch_id']}).status_code == 409
    p = client.post('/api/services/test-service/rating-plan', json={'revision': s['revision']}).json()
    assert client.post('/api/services/test-service/rating-plan/claim', json={'batch_id': p['batch_id']}).status_code == 200
    assert client.post('/api/services/test-service/rating-plan/claim', json={'batch_id': p['batch_id']}).json()['resumed']
    assert client.put('/api/services/test-service/settings', json={'revision': s['revision'], 'settings': s['settings']}).status_code == 409
    assert client.patch('/api/services/test-service/decisions/u0:1', json={'revision': s['revision'], 'state': 'preferred'}).status_code == 409
    valid = {'batch_id': p['batch_id'], 'results': [{'photo_id': i['photo_id'], 'status': 'uncertain'} for i in p['items']]}
    assert client.post('/api/services/test-service/rating-receipts', json=valid).status_code == 200
    assert detail(client)['status'] == 'ready'


def test_quantity_validation_and_no_implicit_cloud(client):
    s = imported(client)
    for target in [0, 5]:
        assert client.put('/api/services/test-service/settings', json={'revision': s['revision'], 'settings': s['settings'] | {'target': target}}).status_code == 422
    s = configure(client, s, mode='hybrid')
    assert client.post('/api/services/test-service/analyze', json={'revision': s['revision']}).status_code == 409
    assert detail(client)['job'] is None

def test_restart_recovers_job_and_decisions(tmp_path):
    app = create_app(tmp_path, token=TOKEN)
    with TestClient(app) as c:
        c.headers['Authorization'] = 'Bearer ' + TOKEN
        s = imported(c)
        store = app.state.store
        with store.transaction() as db:
            s['status'] = 'analyzing'
            s['job'] = {'status': 'running'}
            s['decisions']['u0:1'] = {'state': 'preferred', 'locked': True}
            store.put(db, s)
    with TestClient(create_app(tmp_path, token=TOKEN)) as c:
        c.headers['Authorization'] = 'Bearer ' + TOKEN
        s = detail(c)
        assert s['job']['status'] == 'interrupted'
        assert s['decisions']['u0:1']['locked']


def test_analysis_settings_change_invalidates_rating_proposal(client):
    s = run(client, imported(client))
    s = configure(client, s, target=2)
    assert client.post('/api/services/test-service/rating-plan', json={'revision': s['revision']}).status_code == 409
    s = run(client, s)
    assert client.post('/api/services/test-service/rating-plan', json={'revision': s['revision']}).status_code == 200


def test_duplicated_local_id_is_rejected(client):
    m = manifest()
    m['photos'][1]['local_id'] = m['photos'][0]['local_id']
    assert client.post('/api/imports', json=m).status_code == 422


def test_concurrent_edits_cannot_both_commit_same_revision(client):
    s = imported(client)
    def change(pid):
        return client.patch('/api/services/test-service/decisions/' + pid,
                            json={'revision': s['revision'], 'state': 'preferred', 'locked': True}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = sorted(pool.map(change, ['u0:1', 'u1:1']))
    assert statuses == [200, 409]
    assert len(detail(client)['decisions']) == 1


def test_low_disk_preserves_import_and_does_not_write_preview(client, monkeypatch):
    from collections import namedtuple
    import lrc_selection.app as module
    client.post('/api/imports', json=manifest())
    usage = namedtuple('usage', 'total used free')
    monkeypatch.setattr(module.shutil, 'disk_usage', lambda _: usage(100, 99, 1))
    response = client.put('/api/services/test-service/photos/u0:1/preview', content=jpeg('red'))
    assert response.status_code == 507
    assert detail(client)['status'] == 'importing'
    assert not detail(client)['photos'][0]['preview_ready']


def test_connection_token_does_not_reset_active_job(client):
    from lrc_selection.app import load_connection_token
    store = client.app.state.store
    s = imported(client)
    with store.transaction() as db:
        s['job'] = {'status': 'running'}
        s['status'] = 'analyzing'
        store.put(db, s)
    assert len(load_connection_token(store.root)) > 20
    assert store.get(s['id'])['job']['status'] == 'running'


def test_second_server_cannot_reset_first_servers_jobs(client):
    store = client.app.state.store
    imported(client)
    with pytest.raises(RuntimeError, match='backend usa già'):
        with TestClient(create_app(store.root, token=TOKEN)):
            pass
    assert detail(client)['status'] == 'ready'


def test_cancelled_before_attempt_can_be_retried(client):
    s = imported(client, manifest(count=1))
    plan = client.post('/api/services/test-service/rating-plan', json={'revision': s['revision']}).json()
    client.post('/api/services/test-service/rating-plan/claim', json={'batch_id': plan['batch_id']}).raise_for_status()
    client.post('/api/services/test-service/rating-receipts', json={'batch_id': plan['batch_id'], 'results': [{'photo_id': 'u0:1', 'status': 'skipped'}]}).raise_for_status()
    s = detail(client)
    new = client.post('/api/services/test-service/rating-plan', json={'revision': s['revision']}).json()
    assert len(new['items']) == 1
