"""Confirmed cloud workflow against a fake transport and synthetic JPEGs only."""
import json
import threading
import time

import pytest

from lrc_selection import openai_analysis as api_module
from lrc_selection.engine import analyze
from test_workflow import client, jpeg, manifest


class Secrets:
    reads = 0
    def get(self):
        self.reads += 1
        return 'synthetic-secret-never-returned'


def setup(client, *, duplicate=False):
    runner = client.app.state.openai_analysis
    config = client.app.state.openai_config
    config.path.write_text(json.dumps({'model': api_module.MODEL}))
    config.keychain = Secrets()
    m = manifest(count=3)
    m['photos'][2]['baseline_rating'] = 4
    client.post('/api/imports', json=m).raise_for_status()
    for index, color in enumerate(['red', 'red' if duplicate else 'blue', 'green']):
        client.put(f'/api/services/test-service/photos/u{index}:1/preview', content=jpeg(color)).raise_for_status()
    client.post('/api/services/test-service/complete').raise_for_status()
    store = client.app.state.store
    with store.transaction() as db:
        s = store.get('test-service', db)
        s['settings'].update(mode='hybrid', instructions='  Solo uccelli\nÈ importante: ali aperte!  ', service_criteria=['Preferire varianti'], target=1)
        s['proposal'] = analyze(s)
        store.put(db, s)
    return runner, store.get('test-service')


def reply(*, match='yes', tokens=True):
    result = {'id': 'resp_synthetic', 'model': api_module.MODEL, 'status': 'completed',
              'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps({
                  'match': match, 'reason': 'Evidenza sintetica', 'scene': 'Scena sintetica',
                  'quality_issues': [], 'preference_score': .8})}]}]}
    if tokens:
        result['usage'] = {'input_tokens': 200, 'output_tokens': 50, 'input_tokens_details': {'cached_tokens': 0}}
    return result


def estimate(client, service, budget=1, ids=None):
    return client.post('/api/services/test-service/api-estimate', json={'revision': service['revision'], 'budget_usd': budget,
        'photo_ids': ids or ['u0:1', 'u1:1']})


def confirm(client, plan, **extra):
    return client.post('/api/services/test-service/api-confirm', json={'plan_id': plan['plan_id'], 'confirm': True} | extra)


def wait(client):
    for _ in range(300):
        status = client.get('/api/services/test-service/api-status').json()
        if status['job']['status'] != 'running':
            # Plan status precedes final service transaction by a few instructions.
            for _ in range(100):
                if client.get('/api/services/test-service').json()['status'] == 'ready':
                    return status
                time.sleep(.005)
        time.sleep(.01)
    pytest.fail('Synthetic API job did not finish')


def test_confirmation_required_original_text_preview_scope_and_ratings(client):
    runner, service = setup(client)
    calls = []
    runner.transport = lambda payload, key: calls.append((payload, key)) or reply()
    plan = estimate(client, service).json()
    assert plan['instructions'] == service['settings']['instructions']
    assert len(plan['photos']) == 2 and plan['reserve_usd'] > plan['estimated_cost_usd']
    assert not calls and client.app.state.openai_config.keychain.reads == 0
    assert confirm(client, plan, confirm=False).status_code == 409
    assert not calls
    assert confirm(client, plan).status_code == 200
    done = wait(client)
    assert done['job']['status'] == 'completed' and len(calls) == 2
    for payload, key in calls:
        assert key == 'synthetic-secret-never-returned'
        assert payload['input'][1]['content'][0]['text'] == service['settings']['instructions']
        assert payload['input'][1]['content'][1]['image_url'].startswith('data:image/jpeg;base64,')
        assert payload['input'][1]['content'][1]['detail'] == 'high'
        assert payload['store'] is False and payload['reasoning']['effort'] == 'none'
        assert 'duplicate-name' not in json.dumps(payload)
    updated = client.get('/api/services/test-service').json()
    assert updated['decisions'] == {} and updated['photos'][2]['baseline_rating'] == 4
    assert updated['proposal']['shortlist'] == ['u0:1']
    assert confirm(client, plan).status_code == 409
    assert done['spent_usd'] > 0 and done['reserved_usd'] == 0
    assert done['usage'] == {'input_tokens': 400, 'output_tokens': 100}
    assert done['receipts'][0]['response_id'] == 'resp_synthetic'
    assert 'synthetic-secret' not in json.dumps(done)


def test_budget_cache_duplicatehash_resume_and_cumulative_accounting(client):
    runner, service = setup(client, duplicate=True)
    calls = []
    runner.transport = lambda payload, key: calls.append(payload) or reply()
    plan = estimate(client, service).json()
    assert plan['uncached_count'] == 1
    small = estimate(client, service, budget=.000001).json()
    assert not small['can_confirm']
    assert confirm(client, small).status_code == 409
    plan = estimate(client, service).json()
    confirm(client, plan).raise_for_status()
    status = wait(client)
    assert len(calls) == 1
    current = client.get('/api/services/test-service').json()
    again = estimate(client, current).json()
    assert again['cached_count'] == 2 and again['reserve_usd'] == 0
    confirm(client, again).raise_for_status()
    assert wait(client)['spent_usd'] == status['spent_usd'] and len(calls) == 1
    assert estimate(client, client.get('/api/services/test-service').json(), budget=.000001).status_code == 409


def test_timeout_keeps_reservation_no_auto_retry(client):
    runner, service = setup(client)
    count = []
    def fail(payload, key):
        count.append(1)
        raise TimeoutError('private response body and secret')
    runner.transport = fail
    plan = estimate(client, service).json()
    confirm(client, plan).raise_for_status()
    status = wait(client)
    assert status['job']['status'] == 'paused' and count == [1]
    assert status['reserved_usd'] > 0 and status['spent_usd'] == 0
    assert 'secret' not in json.dumps(status)
    assert client.get('/api/services/test-service').json()['proposal'] == service['proposal']
    # Recovery never sends and retains the uncertain reservation.
    restarted = api_module.OpenAIAnalysis(client.app, client.app.state.store, runner.executor, runner.present, runner.require_editable)
    assert restarted.status('test-service')['reserved_usd'] == status['reserved_usd']
    assert count == [1]


@pytest.mark.parametrize('change', ['revision', 'model', 'preview'])
def test_stale_confirmation_never_sends(client, change):
    runner, service = setup(client)
    runner.transport = lambda *_: pytest.fail('Unexpected transmission')
    plan = estimate(client, service).json()
    if change == 'model':
        client.app.state.openai_config.path.write_text(json.dumps({'model': 'gpt-5.4-2026-03-05'}))
    elif change == 'preview':
        client.app.state.store.preview_path('test-service', 'u0:1').write_bytes(jpeg('black'))
    else:
        with client.app.state.store.transaction() as db:
            changed = client.app.state.store.get('test-service', db)
            changed['revision'] += 1
            client.app.state.store.put(db, changed)
    assert confirm(client, plan).status_code == 409


def test_cancel_after_inflight_request_and_manual_precedence(client):
    runner, service = setup(client)
    entered, release = threading.Event(), threading.Event()
    calls = []
    def blocked(payload, key):
        calls.append(payload)
        entered.set()
        assert release.wait(3)
        return reply()
    runner.transport = blocked
    with client.app.state.store.transaction() as db:
        service = client.app.state.store.get('test-service', db)
        service['decisions'] = {'u2:1': {'state': 'preferred', 'locked': True}, 'u1:1': {'state': 'excluded', 'locked': True}}
        client.app.state.store.put(db, service)
    plan = estimate(client, service).json()
    confirm(client, plan).raise_for_status()
    assert entered.wait(3)
    client.post('/api/services/test-service/api-cancel', json={'plan_id': plan['plan_id']}).raise_for_status()
    release.set()
    assert wait(client)['job']['status'] == 'cancelled' and len(calls) == 1
    current = client.get('/api/services/test-service').json()
    assert current['decisions'] == service['decisions']
    runner.transport = lambda *_: reply(match='no')
    new = estimate(client, current).json()
    confirm(client, new).raise_for_status()
    assert wait(client)['job']['status'] == 'completed'
    current = client.get('/api/services/test-service').json()
    assert current['proposal']['shortlist'][0] == 'u2:1'
    assert 'u1:1' not in current['proposal']['shortlist']


def test_usage_missing_keeps_reserve_and_no_match_never_fills(client):
    runner, service = setup(client)
    runner.transport = lambda *_: reply(tokens=False)
    confirm(client, estimate(client, service).json()).raise_for_status()
    assert wait(client)['reserved_usd'] > 0
    service = client.get('/api/services/test-service').json()
    runner.transport = lambda *_: reply(match='no')
    confirm(client, estimate(client, service).json()).raise_for_status()
    assert wait(client)['job']['status'] == 'completed'
    assert client.get('/api/services/test-service').json()['proposal']['shortlist'] == []


def test_pricing_expiry_blocks_estimates_and_confirmations(client, monkeypatch):
    from datetime import date
    runner, service = setup(client)
    plan = estimate(client, service).json()
    class FutureDate(date):
        @classmethod
        def today(cls):
            return cls(2027, 2, 1)
    monkeypatch.setattr(api_module, 'date', FutureDate)
    runner.transport = lambda *_: pytest.fail('Expired pricing must not send')
    assert estimate(client, service).status_code == 409
    assert confirm(client, plan).status_code == 409


def test_unknown_photo_and_local_mode_cannot_create_send_plan(client):
    runner, service = setup(client)
    assert estimate(client, service, ids=['not-present']).status_code == 422
    with client.app.state.store.transaction() as db:
        service['settings']['mode'] = 'local'
        client.app.state.store.put(db, service)
    assert estimate(client, service).status_code == 409


def test_old_budget_plan_cannot_use_new_budget(client):
    runner, service = setup(client)
    runner.transport = lambda *_: pytest.fail('Old budget plan must not transmit')
    old = estimate(client, service, budget=1).json()
    assert estimate(client, service, budget=2).status_code == 200
    assert confirm(client, old).status_code == 409


def test_transcoded_preview_strips_embedded_metadata(client):
    import base64
    import io
    from PIL import Image
    runner, service = setup(client)
    image = Image.new('RGB', (1700, 1000), 'red')
    exif = Image.Exif()
    exif[270] = 'private metadata must never leave'
    encoded = io.BytesIO()
    image.save(encoded, 'JPEG', exif=exif)
    payload = api_module._request({'model': api_module.MODEL, 'instructions': 'original', 'criteria': [], 'subject_query': ''}, encoded.getvalue())
    sent = base64.b64decode(payload['input'][1]['content'][1]['image_url'].split(',', 1)[1])
    assert b'private metadata' not in sent
    with Image.open(io.BytesIO(sent)) as preview:
        assert max(preview.size) <= 1200 and not preview.getexif()


def test_refusal_with_output_text_is_not_accepted_and_usage_recorded(client):
    runner, service = setup(client)
    def refuse(*_):
        response = reply()
        response['output'][0]['content'].append({'type': 'refusal', 'refusal': 'No assessment'})
        return response
    runner.transport = refuse
    confirm(client, estimate(client, service).json()).raise_for_status()
    status = wait(client)
    assert status['job']['status'] == 'paused'
    assert status['spent_usd'] > 0 and status['reserved_usd'] == 0
    assert client.get('/api/services/test-service').json()['proposal'] == service['proposal']


def test_uncertain_results_do_not_claim_absence(client):
    runner, service = setup(client)
    runner.transport = lambda *_: reply(match='uncertain')
    confirm(client, estimate(client, service).json()).raise_for_status()
    wait(client)
    proposal = client.get('/api/services/test-service').json()['proposal']
    assert proposal['shortlist'] == []
    assert any('non verificabili' in warning for warning in proposal['warnings'])
    assert not any('Nessuna corrispondenza rilevata' in warning for warning in proposal['warnings'])


def test_constructor_does_not_pause_live_plan_until_explicit_locked_recovery(client):
    runner, service = setup(client)
    plan = estimate(client, service).json()
    with runner.db() as db:
        stored = runner.plan(db, service['id'], plan['plan_id'])
        stored['status'] = 'running'
        runner.save(db, stored)
    other = api_module.OpenAIAnalysis(client.app, client.app.state.store, runner.executor, runner.present, runner.require_editable)
    assert other.status(service['id'])['job']['status'] == 'running'
    other.recover()
    assert other.status(service['id'])['job']['status'] == 'paused'
