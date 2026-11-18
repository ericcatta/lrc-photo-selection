import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lrc_selection.openai_config import OpenAIConfig, OpenAIConfigInput, build_responses_request, register_openai_config


class SyntheticKeychain:
    def __init__(self):
        self.key = None
    def get(self):
        return self.key
    def set(self, key):
        self.key = key


def test_config_keeps_secret_only_in_keychain_and_never_returns_it(tmp_path):
    keychain = SyntheticKeychain()
    app = FastAPI()
    register_openai_config(app, tmp_path, keychain=keychain)
    with TestClient(app) as client:
        assert client.get('/api/openai/config').json()['configured'] is False
        secret = 'synthetic-api-secret-not-a-real-key'
        response = client.put('/api/openai/config', json={'model': 'synthetic-model', 'api_key': secret})
        assert response.status_code == 200
        assert secret not in response.text
        assert response.json()['configured'] is True
        assert response.json()['analysis_enabled'] is False
        assert keychain.key == secret
        assert secret not in (tmp_path/'openai-config.json').read_text()
        assert json.loads((tmp_path/'openai-config.json').read_text()) == {'schema_version': 1, 'model': 'synthetic-model'}
        assert (tmp_path/'openai-config.json').stat().st_mode & 0o777 == 0o600
        client.put('/api/openai/config', json={'model': 'changed-model'})
        assert keychain.key == secret
        assert client.get('/api/openai/config').json()['model'] == 'changed-model'


def test_keychain_failure_does_not_fallback_to_plaintext(tmp_path):
    class FailedKeychain(SyntheticKeychain):
        def set(self, key):
            raise RuntimeError('synthetic failure with sensitive details')
    app = FastAPI()
    register_openai_config(app, tmp_path, keychain=FailedKeychain())
    with TestClient(app) as client:
        response = client.put('/api/openai/config', json={'model': 'test', 'api_key': 'synthetic-secret'})
    assert response.status_code == 503
    assert 'synthetic-secret' not in response.text
    assert 'sensitive' not in response.text
    assert not list(tmp_path.iterdir())


def test_config_model_validation_and_secret_repr():
    body = OpenAIConfigInput(api_key='synthetic-secret')
    assert 'synthetic-secret' not in repr(body)
    with pytest.raises(ValueError):
        OpenAIConfigInput(model='https://untrusted/model')


@pytest.mark.parametrize('instructions', ['  Scegli gli uccelli.\nNon perdere l’abbraccio!  ', '\tÈ importante: posa «seria», poi risata.\n\n', ''])
def test_responses_request_preserves_user_instructions_exactly(instructions):
    preview = b'\xff\xd8\xffsynthetic-jpeg-preview'
    result = build_responses_request('synthetic-model', instructions, [preview], context='ID sintetico p0')
    assert result['input'][1]['content'][0] == {'type': 'input_text', 'text': instructions}
    assert result['input'][0]['role'] == 'developer'
    assert result['store'] is False
    assert 'tools' not in result
    assert result['input'][1]['content'][1]['image_url'].startswith('data:image/jpeg;base64,')
    assert 'api_key' not in result


@pytest.mark.parametrize('previews', [[], [b'RAW synthetic'], ['file:///private/photo.jpg']])
def test_responses_builder_rejects_non_preview_payloads(previews):
    with pytest.raises(ValueError):
        build_responses_request('test', 'test', previews)


def test_invalid_key_input_is_not_echoed_by_validation(tmp_path):
    app = FastAPI()
    register_openai_config(app, tmp_path, keychain=SyntheticKeychain())
    with TestClient(app) as client:
        response = client.put('/api/openai/config', json={'api_key': ['synthetic-private-secret']})
    assert response.status_code == 422
    assert 'synthetic-private-secret' not in response.text
