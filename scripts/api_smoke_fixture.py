"""Synthetic API UI only: transport is replaced before the HTTP server starts."""
import argparse
import json
import tempfile
import time
from pathlib import Path

from smoke_fixture import make_app
from lrc_selection.engine import analyze
from lrc_selection.openai_analysis import MODEL

ORIGINAL = '  Conserva le forme sintetiche blu.\nPreferisci varianti differenti!  \n'


class SyntheticSecrets:
    def get(self):
        return 'synthetic-only-key-no-external-access'


def build_fixture(root):
    app = make_app(root)
    app.state.openai_config.keychain = SyntheticSecrets()
    app.state.openai_config.path.write_text(json.dumps({'model': MODEL}))
    store = app.state.store
    with store.transaction() as db:
        service = store.get('synthetic-ui', db)
        service['title'] = 'TEST API SINTETICO — nessuna foto reale'
        service['settings'].update(mode='hybrid', instructions=ORIGINAL, service_criteria=[], target=1)
        service['proposal'] = analyze(service)
        service['proposal']['shortlist'] = ['synthetic-0', 'synthetic-1']
        service['proposal']['shortlist_reasons'] = {pid: 'Proposta simulata per test' for pid in service['proposal']['shortlist']}
        store.put(db, service)
    calls = []

    def synthetic_transport(payload, key):
        assert key == 'synthetic-only-key-no-external-access'
        assert payload['input'][1]['content'][0]['text'] == ORIGINAL
        assert payload['store'] is False
        kind=payload['text']['format']['name']
        if kind!='requested_categories':
            assert payload['input'][1]['content'][1]['image_url'].startswith('data:image/jpeg;base64,')
        calls.append({'original_text_preserved': True})
        time.sleep(.15)
        if kind=='requested_categories':
            assessment={'requested_categories':[{'id':'forms','description':'Forme sintetiche blu'}],'ambiguities':[],'unsupported':[]}
        elif kind=='collection_ranking':
            marker='\nValutazioni di TUTTE le anteprime, indici dei provini: '
            records=json.loads(payload['input'][0]['content'][0]['text'].split(marker,1)[1])
            assessment={'ranking':[record['index'] for record in records if record['assessment']['match']=='yes'],'warnings':[]}
        else:
            assert kind=='photo_assessment'
            assessment={'match':'yes','reason':'Forma blu sintetica verificata dalla simulazione.','scene':'Scena sintetica','quality_issues':[],'preference_score':.8,'category_matches':{'forms':'yes'}}
        return {'id': 'resp_synthetic_' + str(len(calls)), 'model': MODEL, 'status': 'completed',
                'usage': {'input_tokens': 220, 'output_tokens': 65},
                'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(assessment)}]}]}

    app.state.openai_analysis.transport = synthetic_transport

    @app.get('/api/synthetic-transport-status')
    def transport_status():
        return {'mock_calls': len(calls), 'original_text_preserved': all(c['original_text_preserved'] for c in calls),
                'real_network_calls': 0}

    # The app's static catch-all is already mounted: keep test-only routes before it.
    app.router.routes.insert(0, app.router.routes.pop())

    @app.post('/api/synthetic-empty-proposal')
    def empty_proposal():
        with store.transaction() as db:
            service = store.get('synthetic-ui', db)
            service['decisions'] = {}
            service['proposal'] = analyze(service)
            service['proposal'].update(shortlist=[], review_ids=[], shortlist_accepted=False)
            service['job'] = None
            service.pop('confirmed_batch_id', None)
            service['revision'] += 1
            store.put(db, service)
        return {'ok': True}

    app.router.routes.insert(0, app.router.routes.pop())
    return app


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=18766)
    args = parser.parse_args()
    root = Path(tempfile.mkdtemp(prefix='lrc-api-synthetic-'))
    app = build_fixture(root)
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=args.port, access_log=False)
