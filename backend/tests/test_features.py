import importlib.util
from pathlib import Path
from lrc_selection.features import extract
from test_workflow import imported

# Reuse API fixture; no model installation or real photograph involved.
from test_workflow import client

class FakeEncoder:
    identity = {'adapter': 'synthetic-test-only'}
    def encode(self, path):
        assert path.suffix == '.jpg'
        return [1.0, 0.0]

def test_optional_features_do_not_remove_candidates(client):
    s = imported(client)
    before = client.get('/api/services/' + s['id']).json()
    evidence = extract(client.app.state.store, s['id'], FakeEncoder())
    after = client.get('/api/services/' + s['id']).json()
    assert before['selected_ids'] == after['selected_ids']
    assert after['decisions'] == before['decisions']
    assert all(r['error'] == 'Anteprima mancante' for r in evidence['records'].values())
    assert after['interpretations']['model']['adapter'] == 'synthetic-test-only'

def test_benchmark_detects_loss_and_merge(client):
    spec = importlib.util.spec_from_file_location('benchmark', Path(__file__).resolve().parents[2] / 'scripts/benchmark.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    s = imported(client)
    s['proposal'] = {'selected': ['u0:1'], 'groups': [{'members': ['u0:1', 'u1:1']}], 'engine': 'synthetic'}
    result = module.evaluate(s, {'service_id': s['id'], 'significant_groups': [['u2:1']],
                                 'unique_images': ['u3:1'], 'must_separate_pairs': [['u0:1', 'u1:1']]})
    assert result['significant_groups_lost'] == 1
    assert result['unique_images_excluded'] == 1
    assert result['person_compositions_merged'] == 1


def test_apple_vision_processes_synthetic_preview(tmp_path):
    import sys
    import pytest
    from PIL import Image
    from lrc_selection.features import face_rectangles
    tool = Path(__file__).resolve().parents[2] / '.build/lrc-face-detection'
    if sys.platform != 'darwin' or not tool.exists():
        pytest.skip('Apple Vision requires a compiled macOS helper')
    preview = tmp_path / 'synthetic.jpg'
    Image.new('RGB', (100, 100), 'gray').save(preview)
    result = face_rectangles(tool, preview)
    assert result['observations'] == []
    assert result['error'] is None
