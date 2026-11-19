"""Reviewed vision models/pricing; account discovery never sends photographs."""
import json
import os
import ssl
import certifi
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from fastapi import HTTPException

MODEL_SPECS = {
    'gpt-5.4-mini-2026-03-17': {
        'id': 'gpt-5.4-mini-2026-03-17', 'label': 'GPT-5.4 mini',
        'input_per_million': .75, 'output_per_million': 4.5,
        'source': 'https://developers.openai.com/api/docs/models/gpt-5.4-mini', 'verified_at': '2026-11-18',
    },
    'gpt-5.4-2026-03-05': {
        'id': 'gpt-5.4-2026-03-05', 'label': 'GPT-5.4',
        'input_per_million': 2.5, 'output_per_million': 15.,
        'source': 'https://developers.openai.com/api/docs/models/gpt-5.4', 'verified_at': '2026-11-18',
    },
}
ALIASES = {'gpt-5.4-mini': 'gpt-5.4-mini-2026-03-17', 'gpt-5.4': 'gpt-5.4-2026-03-05'}


def lookup_model(model):
    canonical = ALIASES.get(model, model)
    if canonical not in MODEL_SPECS:
        raise ValueError('Modello non supportato o tariffa non verificata. Scegli un modello dalla lista.')
    return dict(MODEL_SPECS[canonical])


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError('Reindirizzamento API rifiutato')


def fetch_account_models(key):
    request = urllib.request.Request('https://api.openai.com/v1/models', headers={'Authorization': 'Bearer '+key})
    with urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=certifi.where()))).open(request, timeout=20) as response:
        raw = response.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError('Elenco modelli non valido')
    data = json.loads(raw)
    if not isinstance(data, dict) or not isinstance(data.get('data'), list):
        raise ValueError('Elenco modelli non valido')
    return {item['id'] for item in data['data'] if isinstance(item, dict) and isinstance(item.get('id'), str) and len(item['id']) <= 200}


class ModelCatalog:
    def __init__(self, root, config):
        self.path = Path(root) / 'openai-available-models.json'
        self.config = config
        self.transport = fetch_account_models

    def read(self):
        cached = json.loads(self.path.read_text()) if self.path.exists() else None
        available = set(cached['ids']) if cached else None
        models = [dict(spec, supported=True, available=(spec['id'] in available if available is not None else None))
                  for spec in MODEL_SPECS.values()]
        if available is not None:
            for model in sorted(available.difference(MODEL_SPECS).difference(ALIASES)):
                models.append({'id': model, 'label': model, 'available': True, 'supported': False,
                               'input_per_million': None, 'output_per_million': None})
        checked_at = cached['checked_at'] if cached else None
        stale = not checked_at or (datetime.now(timezone.utc) - datetime.fromisoformat(checked_at)).total_seconds() > 86400
        return {'models': models, 'checked_at': checked_at, 'stale': stale,
                'note': 'Elenco disponibile dall’account, aggiornabile da OpenAI. I modelli nuovi/altri richiedono verifica di compatibilità e tariffa prima dell’analisi. Nessuna sostituzione automatica del modello scelto.'}

    def refresh(self):
        try:
            key = self.config.secrets().get()
            if not key:
                raise HTTPException(409, 'Salva prima la chiave API nella configurazione.')
            available = self.transport(key)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(502, 'Verifica modelli non riuscita. Controlla chiave, permessi e connessione; nessuna foto inviata.') from None
        record = {'ids': sorted(set(available)),
                  'checked_at': datetime.now(timezone.utc).isoformat()}
        temporary = self.path.with_suffix('.pending')
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump(record, stream)
        temporary.replace(self.path)
        return self.read()


def register_model_catalog(app, root):
    catalog = ModelCatalog(root, app.state.openai_config)
    app.state.openai_models = catalog
    @app.get('/api/openai/models')
    def models():
        return catalog.read()
    @app.post('/api/openai/models/refresh')
    def refresh_models():
        return catalog.refresh()
