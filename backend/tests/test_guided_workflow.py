"""Navigation reflects saved facts; summaries never trigger analysis or ratings."""
from copy import deepcopy

from lrc_selection.models import Settings
from lrc_selection.workflow import workflow_summary
from test_workflow import client, imported, configure
from test_openai_analysis import setup, estimate


def service():
    return {'revision': 4, 'status': 'ready', 'settings': {'mode': 'local', 'target': 15},
            'photos': [{'id': 'one'}, {'id': 'two'}], 'decisions': {}, 'receipts': [], 'job': None, 'proposal': None}


def test_workflow_routes_and_legacy_settings():
    assert Settings(target=1, mode='hybrid').workflow_path is None
    assert Settings(target=1, workflow_path='openai').mode == 'hybrid'
    assert Settings(target=1, mode='hybrid', workflow_path='local').mode == 'local'
    s = service()
    before = deepcopy(s)
    assert workflow_summary(s)['phase'] == 'configure'
    assert s == before
    s['proposal'] = {'shortlist': ['one'], 'selected': ['one', 'two']}
    assert workflow_summary(s)['phase'] == 'review'
    s['settings']['mode'] = 'hybrid'
    assert workflow_summary(s)['phase'] == 'analyze'
    s['proposal']['api_plan_id'] = 'api-plan'
    s['proposal']['api_target'] = 1
    summary = workflow_summary(s)
    assert summary['phase'] == 'review' and summary['target'] == 1
    s['proposal']['shortlist_accepted'] = True
    assert workflow_summary(s)['phase'] == 'lightroom'
    s['confirmed_batch_id'] = 'batch'
    assert workflow_summary(s)['confirmed_batch_id'] == 'batch'
    del s['confirmed_batch_id']
    s['proposal']['stale'] = True
    assert workflow_summary(s)['phase'] == 'configure'


def test_outcome_requires_current_receipt_and_reports_partial():
    s = service()
    s['receipts'] = [{'batch_id': 'batch', 'results': [{'status': 'applied'}, {'status': 'conflict'}]}]
    summary = workflow_summary(s, receipt_revision=4)
    assert summary['phase'] == 'outcome'
    assert summary['outcome'] == {'applied': 1, 'skipped': 0, 'conflict': 1, 'uncertain': 0, 'total': 2}
    s['revision'] = 5
    assert workflow_summary(s, receipt_revision=4)['outcome'] is None
    s['job'] = {'status': 'running'}
    assert workflow_summary(s)['phase'] == 'analyze'


def test_settings_public_summary_and_direct_route_are_compatible(client):
    s = imported(client)
    assert s['workflow']['schema_version'] == 1
    assert s['workflow']['path'] == 'local'
    s = configure(client, s, workflow_path='openai')
    assert s['settings']['mode'] == 'hybrid'
    assert s['workflow']['path'] == 'openai'
    assert s['workflow']['phase'] == 'configure'


def test_resume_reuses_exact_sample_even_after_new_estimate(client):
    runner, s = setup(client)
    first = estimate(client, s, ids=['u1:1', 'u0:1']).json()
    with runner.db() as db:
        plan = runner.plan(db, s['id'], first['plan_id'])
        plan.update(status='paused', completed=1)
        runner.save(db, plan)
    # Another estimate must not hide the sample of the interrupted attempt.
    estimate(client, s, ids=['u2:1']).raise_for_status()
    status = client.get('/api/services/test-service/api-status').json()
    assert status['resume'] == {'plan_id': first['plan_id'], 'photo_ids': ['u1:1', 'u0:1'],
                                'compatible': True, 'reason': '', 'completed': 1, 'total': 2, 'final_target': 1}
    assert status['job']['status'] == 'estimated'
    store = client.app.state.store
    with store.transaction() as db:
        changed = store.get(s['id'], db)
        changed['settings']['instructions'] += 'changed'
        store.put(db, changed)
    resume = client.get('/api/services/test-service/api-status').json()['resume']
    assert not resume['compatible'] and 'criteri' in resume['reason']
