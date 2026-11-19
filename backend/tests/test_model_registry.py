import json
from datetime import datetime, timedelta, timezone
import pytest
from fastapi import HTTPException
from lrc_selection.model_registry import ModelCatalog, lookup_model, NoRedirect
from lrc_selection.openai_config import OpenAIConfig, OpenAIConfigInput

class Keys:
    def __init__(self): self.calls = 0; self.value = 'synthetic-only-key'
    def get(self): self.calls += 1; return self.value
    def set(self, value): self.value = value


def test_discovery_is_explicit_and_new_models_appear_without_inventing_prices(tmp_path):
    keys = Keys(); config = OpenAIConfig(tmp_path, keys); catalog = ModelCatalog(tmp_path, config)
    assert catalog.read()['stale']
    assert keys.calls == 0
    calls = []
    def fetch(key):
        calls.append(key)
        return {'gpt-5.4-mini-2026-03-17', 'future-vision-model'}
    catalog.transport = fetch
    view = catalog.refresh()
    assert len(calls) == 1
    assert not view['stale']
    new = next(m for m in view['models'] if m['id'] == 'future-vision-model')
    assert new['available'] and not new['supported'] and new['input_per_million'] is None
    assert not next(m for m in view['models'] if m['id']=='gpt-5.4-2026-03-05')['available']
    assert 'synthetic-only-key' not in catalog.path.read_text()
    catalog.read()
    assert len(calls) == 1
    with pytest.raises(ValueError): lookup_model('future-vision-model')
    cached = json.loads(catalog.path.read_text())
    cached['checked_at'] = (datetime.now(timezone.utc)-timedelta(days=2)).isoformat()
    catalog.path.write_text(json.dumps(cached))
    assert catalog.read()['stale']
    config.save(OpenAIConfigInput(model='gpt-5.4-mini', api_key='synthetic-new-key'))
    assert not catalog.path.exists()


def test_model_change_changes_tariff_and_unknown_models_fail_closed():
    assert lookup_model('gpt-5.4')['output_per_million'] > lookup_model('gpt-5.4-mini')['output_per_million']
    assert lookup_model('gpt-5.4-mini')['id'] == 'gpt-5.4-mini-2026-03-17'
    with pytest.raises(ValueError): lookup_model('arbitrary')


def test_discovery_errors_do_not_expose_credentials(tmp_path):
    catalog = ModelCatalog(tmp_path, OpenAIConfig(tmp_path, Keys()))
    def failure(key): raise RuntimeError('upstream echo '+key)
    catalog.transport = failure
    with pytest.raises(HTTPException) as exc: catalog.refresh()
    assert 'synthetic-only-key' not in str(exc.value.detail)
    with pytest.raises(RuntimeError): NoRedirect().redirect_request(None,None,302,'',{},'https://example.com')


def test_account_vision_families_are_usable_without_invented_tariffs(tmp_path):
    catalog = ModelCatalog(tmp_path, OpenAIConfig(tmp_path, Keys()))
    catalog.transport = lambda key: {'gpt-6.2-sol', 'gpt-6.2-astra', 'gpt-6.1-terra', 'gpt-5.6-luna', 'gpt-4.1-mini', 'o3', 'gpt-audio', 'text-embedding-3-small', 'gpt-4o-realtime-preview', 'gpt-image-1', 'gpt-5.4-pro'}
    models = {model['id']: model for model in catalog.refresh()['models']}
    assert models['gpt-6.2-sol']['supported'] and models['gpt-6.2-sol']['input_per_million'] == 2
    assert models['gpt-6.2-astra']['output_per_million'] == 40
    for name in ['gpt-6.1-terra', 'gpt-5.6-luna', 'gpt-4.1-mini', 'o3']:
        assert models[name]['supported'] and models[name]['available']
        assert models[name]['pricing_known'] is False and models[name]['input_per_million'] is None
        assert models[name]['compatibility'] == 'family'
    for name in ['gpt-audio', 'text-embedding-3-small', 'gpt-4o-realtime-preview', 'gpt-image-1', 'gpt-5.4-pro']:
        assert not models[name]['supported']


def test_parameters_respect_model_family():
    from lrc_selection.model_registry import request_parameters
    assert request_parameters('gpt-6.2-sol') == {'reasoning': {'effort': 'low'}}
    assert request_parameters('gpt-6.2-astra') == {'reasoning': {'effort': 'low'}}
    assert request_parameters('gpt-5.3-codex') == {'reasoning': {'effort': 'low'}}
    assert request_parameters('gpt-5.4-mini-2026-03-17') == {'reasoning': {'effort': 'none'}}
    assert request_parameters('gpt-4.1-mini') == {}
