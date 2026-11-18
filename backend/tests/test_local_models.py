"""Synthetic files only; no model downloads or inference."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from lrc_selection.local_models import DEFAULT_MODEL, MODELS, SELECTION_FILE, activate_model, model_ready, resolve_model

NEW_MODEL = 'Qwen3.5-9B-MLX-4bit'


def fixture_model(root, model=DEFAULT_MODEL):
    path = root / 'models' / model
    path.mkdir(parents=True)
    (path / 'config.json').write_text('{"model_type":"synthetic"}')
    (path / 'model.safetensors').write_bytes(b'synthetic-not-real-weights')
    return path


def test_resolution_default_selection_and_environment_precedence(tmp_path, monkeypatch):
    monkeypatch.delenv('LRC_VLM_DIR', raising=False)
    old = fixture_model(tmp_path)
    new = fixture_model(tmp_path, NEW_MODEL)
    assert resolve_model(tmp_path) == old
    activate_model(tmp_path, NEW_MODEL)
    assert resolve_model(tmp_path) == new
    monkeypatch.setenv('LRC_VLM_DIR', str(old))
    (tmp_path / SELECTION_FILE).write_text('{"schema_version":1,"model":"unknown"}')
    assert resolve_model(tmp_path) == old
    monkeypatch.delenv('LRC_VLM_DIR')
    with pytest.raises(ValueError):
        resolve_model(tmp_path)


def test_activation_preserves_previous_selection_when_incomplete(tmp_path):
    fixture_model(tmp_path)
    activate_model(tmp_path, DEFAULT_MODEL)
    selection = (tmp_path / SELECTION_FILE).read_bytes()
    new = fixture_model(tmp_path, NEW_MODEL)
    (new / 'model.safetensors.index.json').write_text(json.dumps({'weight_map': {'a': 'missing.safetensors'}}))
    assert not model_ready(new)
    with pytest.raises(ValueError):
        activate_model(tmp_path, NEW_MODEL)
    assert (tmp_path / SELECTION_FILE).read_bytes() == selection
    assert not list(tmp_path.glob('.local-model-*'))
    (new / 'model.safetensors.index.json').write_text('{"weight_map":{"a":"../model.safetensors"}}')
    assert not model_ready(new)


def test_invalid_selection_and_configuration_fail(tmp_path, monkeypatch):
    monkeypatch.delenv('LRC_VLM_DIR', raising=False)
    path = fixture_model(tmp_path)
    (path / 'config.json').write_text('broken')
    assert resolve_model(tmp_path) is None
    for contents in ('broken', '[]', '{"schema_version":2,"model":"'+DEFAULT_MODEL+'"}'):
        (tmp_path / SELECTION_FILE).write_text(contents)
        with pytest.raises(ValueError):
            resolve_model(tmp_path)


def test_setup_pinned_download_and_explicit_activation(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('setup_local_model', Path(__file__).resolve().parents[2] / 'scripts/setup_local_model.py')
    setup = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(setup)
    calls = []
    def download(repo, **kwargs):
        calls.append((repo, kwargs))
        fixture_model(tmp_path, kwargs['local_dir'].name)
    monkeypatch.setitem(sys.modules, 'huggingface_hub', SimpleNamespace(snapshot_download=download))
    setup.main(['--data-dir', str(tmp_path)])
    assert calls[0][0] == MODELS[DEFAULT_MODEL]['repo']
    assert calls[0][1]['revision'] == MODELS[DEFAULT_MODEL]['revision']
    assert not (tmp_path / SELECTION_FILE).exists()
    setup.main(['--data-dir', str(tmp_path), '--model', NEW_MODEL, '--activate'])
    assert calls[1][1]['revision'] == MODELS[NEW_MODEL]['revision']
    assert json.loads((tmp_path / SELECTION_FILE).read_text())['model'] == NEW_MODEL
