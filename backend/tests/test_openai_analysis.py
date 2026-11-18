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


def reply(payload=None, *, match='yes', tokens=True):
    result = {'id': 'resp_synthetic', 'model': api_module.MODEL, 'status': 'completed',
              'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps({
                  'match': match, 'reason': 'Evidenza sintetica', 'scene': 'Scena sintetica',
                  'quality_issues': [], 'preference_score': .8, 'category_matches': {}})}]}]}
    if payload is not None:
        name = payload['text']['format']['name']
        if name == 'requested_categories':
            body = {'requested_categories': [], 'ambiguities': [], 'unsupported': []}
            result['output'][0]['content'][0]['text'] = json.dumps(body)
        elif name == 'collection_ranking':
            context = payload['input'][0]['content'][0]['text']
            records = json.loads(context.split('Valutazioni di TUTTE le anteprime, indici dei provini: ')[1])
            body = {'ranking': [r['index'] for r in records if r['assessment']['match'] == 'yes'], 'warnings': []}
            result['output'][0]['content'][0]['text'] = json.dumps(body)
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
    runner.transport = lambda payload, key: calls.append((payload, key)) or reply(payload)
    plan = estimate(client, service).json()
    assert plan['instructions'] == service['settings']['instructions']
    assert len(plan['photos']) == 2 and plan['reserve_usd'] > plan['estimated_cost_usd']
    assert not calls and client.app.state.openai_config.keychain.reads == 0
    assert confirm(client, plan, confirm=False).status_code == 409
    assert not calls
    assert confirm(client, plan).status_code == 200
    done = wait(client)
    assert done['job']['status'] == 'completed' and len(calls) == 4
    for payload, key in calls:
        assert key == 'synthetic-secret-never-returned'
        assert payload['input'][1]['content'][0]['text'] == service['settings']['instructions']
        if payload['text']['format']['name'] != 'requested_categories':
            assert payload['input'][1]['content'][1]['image_url'].startswith('data:image/jpeg;base64,')
            assert payload['input'][1]['content'][1]['detail'] == 'high'
        assert payload['store'] is False and payload['reasoning']['effort'] == 'none'
        assert 'duplicate-name' not in json.dumps(payload)
    updated = client.get('/api/services/test-service').json()
    assert updated['decisions'] == {} and updated['photos'][2]['baseline_rating'] == 4
    assert updated['proposal']['shortlist'] == ['u0:1']
    assert confirm(client, plan).status_code == 409
    assert done['spent_usd'] > 0 and done['reserved_usd'] == 0
    assert done['usage'] == {'input_tokens': 800, 'output_tokens': 200}
    assert done['receipts'][0]['response_id'] == 'resp_synthetic'
    assert 'synthetic-secret' not in json.dumps(done)


def test_budget_cache_duplicatehash_resume_and_cumulative_accounting(client):
    runner, service = setup(client, duplicate=True)
    calls = []
    runner.transport = lambda payload, key: calls.append(payload) or reply(payload)
    plan = estimate(client, service).json()
    assert plan['uncached_count'] == 1
    small = estimate(client, service, budget=.000001).json()
    assert not small['can_confirm']
    assert confirm(client, small).status_code == 409
    plan = estimate(client, service).json()
    confirm(client, plan).raise_for_status()
    status = wait(client)
    assert len(calls) == 3
    current = client.get('/api/services/test-service').json()
    again = estimate(client, current).json()
    assert again['cached_count'] == 2 and again['reserve_usd'] == 0
    confirm(client, again).raise_for_status()
    assert wait(client)['spent_usd'] == status['spent_usd'] and len(calls) == 3
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
        return reply(payload)
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
    runner.transport = lambda payload, key: reply(payload, match='no')
    new = estimate(client, current).json()
    confirm(client, new).raise_for_status()
    assert wait(client)['job']['status'] == 'completed'
    current = client.get('/api/services/test-service').json()
    assert current['proposal']['shortlist'][0] == 'u2:1'
    assert 'u1:1' not in current['proposal']['shortlist']


def test_usage_missing_keeps_reserve_and_no_match_never_fills(client):
    runner, service = setup(client)
    runner.transport = lambda payload, key: reply(payload, tokens=False)
    confirm(client, estimate(client, service).json()).raise_for_status()
    assert wait(client)['reserved_usd'] > 0
    service = client.get('/api/services/test-service').json()
    runner.transport = lambda payload, key: reply(payload, match='no')
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
    def refuse(payload, key):
        response = reply(payload)
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
    runner.transport = lambda payload, key: reply(payload, match='uncertain')
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


def test_optional_budget_direct_api_and_independent_final_target_reselect(client):
    runner, service = setup(client)
    with client.app.state.store.transaction() as db:
        service['proposal'] = None
        service['settings']['target'] = 3
        client.app.state.store.put(db, service)
    calls = []
    runner.transport = lambda payload, key: calls.append(payload) or reply(payload)
    response = client.post('/api/services/test-service/api-estimate', json={'revision': service['revision'], 'photo_ids': ['u0:1', 'u1:1'], 'target': 1})
    response.raise_for_status()
    plan = response.json()
    assert plan['budget_usd'] is None and plan['can_confirm']
    assert plan['guard_usd'] == plan['reserve_usd'] > 0 and plan['final_target'] == 1
    assert plan['interpretation_request_count'] == plan['collection_request_count'] == 1
    assert plan['request_count'] == 4 and plan['collection_sheet_count'] == 1
    assert not calls
    confirm(client, plan).raise_for_status()
    assert wait(client)['job']['status'] == 'completed'
    current = client.get('/api/services/test-service').json()
    assert current['settings']['target'] == 3 and len(current['proposal']['shortlist']) == 1
    runner.transport = lambda *_: pytest.fail('Reselection must not call OpenAI')
    response = client.post('/api/services/test-service/api-reselect', json={'revision': current['revision'], 'plan_id': plan['plan_id'], 'target': 2})
    response.raise_for_status()
    updated = response.json()
    assert len(updated['proposal']['shortlist']) == 2 and updated['proposal']['api_target'] == 2
    assert updated['settings']['target'] == 3 and updated['decisions'] == {}
    assert len(calls) == 4


def test_global_duplicate_ranking_pauses_without_replacing_proposal(client):
    runner, service = setup(client)
    def invalid_global(payload, key):
        result = reply(payload)
        if payload['text']['format']['name'] == 'collection_ranking':
            result['output'][0]['content'][0]['text'] = json.dumps({'ranking': [0, 0], 'warnings': []})
        return result
    runner.transport = invalid_global
    confirm(client, estimate(client, service).json()).raise_for_status()
    status = wait(client)
    assert status['job']['status'] == 'paused'
    assert status['spent_usd'] > 0 and status['reserved_usd'] == 0
    assert client.get('/api/services/test-service').json()['proposal'] == service['proposal']
    with runner.db() as db:
        plan = runner.plan(db, service['id'], status['job']['plan_id'])
        assert db.execute('SELECT key FROM cache WHERE key=?', (plan['collection_key'],)).fetchone() is None


def test_global_comparison_ranking_and_categories_consider_whole_set(client):
    runner, service = setup(client)
    with client.app.state.store.transaction() as db:
        service['settings']['target'] = 1
        client.app.state.store.put(db, service)
    photo_number = [0]
    categories = [{'id': 'birds', 'description': 'uccelli'}, {'id': 'portraits', 'description': 'ritratti di persone'}]
    def categorized(payload, key):
        result = reply(payload)
        name = payload['text']['format']['name']
        if name == 'requested_categories':
            body = {'requested_categories': categories, 'ambiguities': [], 'unsupported': []}
        elif name == 'photo_assessment':
            n = photo_number[0]
            photo_number[0] += 1
            body = {'match': 'yes', 'reason': 'Foto pertinente sintetica', 'scene': 'Scena sintetica', 'quality_issues': [],
                    'preference_score': .9 if n == 0 else .2, 'category_matches': {'birds': 'yes' if n == 0 else 'no', 'portraits': 'yes' if n == 1 else 'no'}}
            schema = payload['text']['format']['schema']['properties']['category_matches']
            assert schema['additionalProperties'] is False and set(schema['required']) == {'birds', 'portraits'}
        else:
            # Global comparison puts a lower individual-scoring portrait first.
            body = {'ranking': [1, 0], 'warnings': []}
            assert len(payload['input'][1]['content']) == 2  # original text + one sheet, no hidden photos
        result['output'][0]['content'][0]['text'] = json.dumps(body)
        assert payload['input'][1]['content'][0]['text'] == service['settings']['instructions']
        return result
    runner.transport = categorized
    confirm(client, estimate(client, service).json()).raise_for_status()
    assert wait(client)['job']['status'] == 'completed'
    proposal = client.get('/api/services/test-service').json()['proposal']
    assert set(proposal['shortlist']) == {'u0:1', 'u1:1'}  # coverage overrides target1
    assert all(c['status'] == 'represented' for c in proposal['coverage'])


def test_duplicate_categories_never_send_photos_or_poison_cache(client):
    runner, service = setup(client)
    calls = []
    def duplicated(payload, key):
        calls.append(payload)
        result = reply(payload)
        result['output'][0]['content'][0]['text'] = json.dumps({'requested_categories': [{'id': 'same', 'description': 'one'}, {'id': 'same', 'description': 'two'}], 'ambiguities': [], 'unsupported': []})
        return result
    runner.transport = duplicated
    confirm(client, estimate(client, service).json()).raise_for_status()
    status = wait(client)
    assert status['job']['status'] == 'paused' and len(calls) == 1
    with runner.db() as db:
        plan = runner.plan(db, service['id'], status['job']['plan_id'])
        assert db.execute('SELECT key FROM cache WHERE key=?', (plan['interpretation_key'],)).fetchone() is None


def test_ambiguous_interpretation_does_not_claim_global_comparison(client):
    runner, service = setup(client)
    def ambiguous(payload, key):
        result = reply(payload)
        result['output'][0]['content'][0]['text'] = json.dumps({'requested_categories': [], 'ambiguities': ['Chiarire il soggetto'], 'unsupported': []})
        return result
    runner.transport = ambiguous
    confirm(client, estimate(client, service).json()).raise_for_status()
    assert wait(client)['job']['status'] == 'completed'
    proposal = client.get('/api/services/test-service').json()['proposal']
    assert any('confronto globale non eseguiti' in warning for warning in proposal['warnings'])
    assert not any('confronto globale dei provini' in warning for warning in proposal['warnings'])


def test_direct_api_clears_pending_local_analysis_after_actual_comparison(client):
    runner, service = setup(client)
    with client.app.state.store.transaction() as db:
        service['requires_analysis'] = True
        service['proposal'] = None
        client.app.state.store.put(db, service)
    runner.transport = lambda payload, key: reply(payload)
    confirm(client, estimate(client, service).json()).raise_for_status()
    wait(client)
    assert not client.get('/api/services/test-service').json().get('requires_analysis')


def test_global_timeout_resumes_from_assessment_cache_without_new_photos(client):
    runner, service = setup(client)
    def global_timeout(payload, key):
        if payload['text']['format']['name'] == 'collection_ranking':
            raise TimeoutError('Uncertain delivery')
        return reply(payload)
    runner.transport = global_timeout
    first = estimate(client, service).json()
    confirm(client, first).raise_for_status()
    status = wait(client)
    assert status['job']['status'] == 'paused' and status['reserved_usd'] > 0
    current = client.get('/api/services/test-service').json()
    next_plan = estimate(client, current).json()
    assert next_plan['cached_count'] == 2 and next_plan['interpretation_cached']
    assert next_plan['request_count'] == next_plan['collection_request_count'] == 1
    calls = []
    runner.transport = lambda payload, key: calls.append(payload) or reply(payload)
    confirm(client, next_plan).raise_for_status()
    resumed = wait(client)
    assert resumed['job']['status'] == 'completed'
    assert len(calls) == 1 and calls[0]['text']['format']['name'] == 'collection_ranking'
    assert resumed['reserved_usd'] == status['reserved_usd']  # unknown earlier result remains reserved


def test_legacy_plans_fail_closed_before_network(client):
    runner, service = setup(client)
    runner.transport = lambda *_: pytest.fail('Legacy plan must not transmit')
    plan = estimate(client, service).json()
    with runner.db() as db:
        legacy = runner.plan(db, service['id'], plan['plan_id'])
        for name in ['schema_version', 'guard_usd', 'collection_key', 'interpretation_key', 'pricing']:
            legacy.pop(name, None)
        runner.save(db, legacy)
    response = confirm(client, plan)
    assert response.status_code == 409 and 'nuova stima' in response.json()['detail']
    with runner.db() as db:
        legacy['status'] = 'completed'
        runner.save(db, legacy)
    response = client.post('/api/services/test-service/api-reselect', json={'revision': service['revision'], 'plan_id': plan['plan_id'], 'target': 1})
    assert response.status_code == 409
    assert client.app.state.openai_config.keychain.reads == 0


def test_actual_payload_guard_blocks_before_transmission(client):
    runner, service = setup(client)
    plan = estimate(client, service).json()
    with runner.db() as db:
        saved = runner.plan(db, service['id'], plan['plan_id'])
        saved['per_call_reserve_micro'] = 1
        runner.save(db, saved)
    runner.transport = lambda *_: pytest.fail('Undersized reserve must not transmit')
    confirm(client, plan).raise_for_status()
    status = wait(client)
    assert status['job']['status'] == 'paused'
    assert 'costo o il contesto' in status['job']['error']
    assert status['spent_usd'] == status['reserved_usd'] == 0
