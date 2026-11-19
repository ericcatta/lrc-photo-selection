"""Synthetic API workflows with a fake local VLM; no model loading or downloads."""
import threading
import time

from PIL import Image
import pytest

from lrc_selection import vlm
from test_workflow import client, jpeg, manifest


@pytest.fixture
def instruction_model(client, monkeypatch):
    model_dir = client.app.state.store.root / 'models' / 'Qwen3-VL-4B-Instruct-4bit'
    model_dir.mkdir(parents=True)
    (model_dir / 'config.json').write_text('{"model_type":"synthetic"}')
    (model_dir / 'synthetic.safetensors').write_bytes(b'SYNTHETIC TEST MARKER, NOT MODEL WEIGHTS')
    monkeypatch.setenv('LRC_VLM_DIR', str(model_dir))
    monkeypatch.setenv('LRC_SIGLIP_DIR', str(model_dir / 'absent-siglip'))

    class FakeVLM:
        identity = {'adapter': 'synthetic-workflow-only'}
        matches = True
        entered = threading.Event()
        release = threading.Event()
        calls = []

        def __init__(self, path):
            assert path == model_dir

        def interpret(self, instructions, criteria):
            self.calls.append(('interpret', instructions, criteria))
            self.entered.set()
            assert self.release.wait(3), 'Synthetic test did not release analysis'
            return {'summary': 'Solo forme rosse sintetiche', 'criteria': ['Forma rossa'],
                    'ambiguities': [], 'unsupported': [], 'category_mode':'any', 'requested_categories': []}

        def assess(self, path, interpretation):
            with Image.open(path) as image:
                red, green, blue = image.getpixel((0, 0))
            self.calls.append(('assess', path))
            return {'match': 'yes' if self.matches and red > green and red > blue else 'no',
                    'reason': 'Colore sintetico verificato', 'scene': 'Forma sintetica', 'quality_issues': [], 'preference_score': .5, 'category_matches': {}}

    monkeypatch.setattr(vlm, 'LocalVLM', FakeVLM)
    yield FakeVLM
    FakeVLM.release.set()


def prepared(client, target=1):
    m = manifest(count=5)
    m['photos'][4]['baseline_rating'] = 3
    client.post('/api/imports', json=m).raise_for_status()
    for index, color in enumerate(['red', 'blue', 'green', 'yellow', 'purple']):
        client.put(f'/api/services/test-service/photos/u{index}:1/preview', content=jpeg(color)).raise_for_status()
    service = client.post('/api/services/test-service/complete').json()
    response = client.put('/api/services/test-service/settings', json={
        'revision': service['revision'],
        'settings': service['settings'] | {'instructions': 'Solo forme rosse sintetiche', 'service_criteria': [], 'target': target},
    })
    response.raise_for_status()
    return response.json()


def analyze(client, service, fake):
    response = client.post('/api/services/test-service/analyze', json={'revision': service['revision']})
    response.raise_for_status()
    assert fake.entered.wait(3)
    assert response.json()['job']['status'] == 'running'
    fake.release.set()
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        result = client.get('/api/services/test-service').json()
        if result['job']['status'] != 'running':
            assert result['job']['status'] == 'completed', result['job']
            return result
        time.sleep(0.01)
    pytest.fail('Synthetic background analysis did not finish')


def test_instruction_analysis_review_acceptance_preserves_manual_work_and_undo(client, instruction_model):
    service = prepared(client, target=2)
    for pid, state, locked in [('u1:1', 'candidate', True), ('u2:1', 'excluded', False), ('u3:1', 'alternative', True)]:
        response = client.patch('/api/services/test-service/decisions/' + pid, json={
            'revision': service['revision'], 'state': state, 'locked': locked, 'confirm_last': True,
        })
        response.raise_for_status()
        service = response.json()
    before = service['decisions']
    ratings = [p['baseline_rating'] for p in service['photos']]
    assert client.get('/api/capabilities').json()['instructions'] is True
    reviewed = analyze(client, service, instruction_model)
    assert reviewed['decisions'] == before
    assert set(reviewed['proposal']['shortlist']) == {'u0:1', 'u1:1', 'u4:1'}
    assert reviewed['proposal']['instruction_interpretation']['summary'] == 'Solo forme rosse sintetiche'
    assert len([call for call in instruction_model.calls if call[0] == 'assess']) == 5
    endpoint = '/api/services/test-service/accept-shortlist'
    assert client.post(endpoint, json={'revision': reviewed['revision']}).status_code == 409
    assert client.post(endpoint, json={'revision': reviewed['revision'] - 1, 'confirm_last': True}).status_code == 409
    accepted = client.post(endpoint, json={'revision': reviewed['revision'], 'confirm_last': True})
    accepted.raise_for_status()
    accepted = accepted.json()
    assert all(accepted['decisions'][pid] == decision for pid, decision in before.items())
    assert accepted['decisions']['u0:1'] == {'state': 'candidate', 'locked': False}
    assert accepted['decisions']['u4:1'] == {'state': 'candidate', 'locked': False}
    assert [p['baseline_rating'] for p in accepted['photos']] == ratings
    assert 'confirmed_batch_id' not in accepted
    restored = client.post('/api/services/test-service/undo', json={'revision': accepted['revision']})
    restored.raise_for_status()
    assert restored.json()['decisions'] == before


def test_no_matching_subject_keeps_shortlist_empty_and_rejects_acceptance(client, instruction_model):
    instruction_model.matches = False
    reviewed = analyze(client, prepared(client), instruction_model)
    assert reviewed['proposal']['shortlist'] == []
    assert reviewed['decisions'] == {}
    response = client.post('/api/services/test-service/accept-shortlist', json={
        'revision': reviewed['revision'], 'confirm_last': True,
    })
    assert response.status_code == 409
    unchanged = client.get('/api/services/test-service').json()
    assert unchanged['decisions'] == {}
    assert unchanged['revision'] == reviewed['revision']


def test_changed_instructions_make_shortlist_stale_and_unacceptable(client, instruction_model):
    reviewed = analyze(client, prepared(client), instruction_model)
    response = client.put('/api/services/test-service/settings', json={
        'revision': reviewed['revision'], 'settings': reviewed['settings'] | {'instructions': 'Solo forme blu sintetiche'},
    })
    response.raise_for_status()
    changed = response.json()
    assert changed['proposal']['stale'] is True
    response = client.post('/api/services/test-service/accept-shortlist', json={
        'revision': changed['revision'], 'confirm_last': True,
    })
    assert response.status_code == 409
    assert client.get('/api/services/test-service').json()['decisions'] == {}
