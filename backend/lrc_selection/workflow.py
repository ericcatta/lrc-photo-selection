"""Read-only, versioned navigation state. Never grants permission for actions."""
from .engine import effective_selected


def workflow_summary(service, receipt_revision=None):
    settings = service['settings']
    path = settings.get('workflow_path') or settings.get('mode', 'local')
    proposal = service.get('proposal') or {}
    job = service.get('job') or {}
    stale = bool(service.get('requires_analysis') or proposal.get('stale'))
    ready = bool(proposal) and not stale
    accepted = ready and ('shortlist' not in proposal or bool(proposal.get('shortlist_accepted')))
    local_completed = ready and not proposal.get('api_plan_id')
    confirmed = service.get('confirmed_batch_id')
    active = service.get('active_batch_id')
    receipts = service.get('receipts', [])
    outcome = None
    if receipts and receipt_revision == service['revision']:
        counts = {key: 0 for key in ('applied', 'skipped', 'conflict', 'uncertain')}
        for result in receipts[-1]['results']:
            counts[result['status']] += 1
        outcome = counts | {'total': len(receipts[-1]['results'])}
    if service['status'] in ('analyzing', 'importing') or job.get('status') in ('running', 'queued', 'cancel_requested'):
        phase = 'analyze'
    elif confirmed or active or service['status'] == 'applying':
        phase = 'lightroom'
    elif outcome is not None:
        phase = 'outcome'
    elif stale:
        phase = 'configure'
    elif accepted:
        phase = 'lightroom'
    elif ready:
        phase = 'analyze' if path == 'hybrid' and local_completed else 'review'
    elif job.get('status') in ('failed', 'interrupted', 'paused', 'cancelled'):
        phase = 'analyze'
    else:
        phase = 'configure'
    return {'schema_version': 1, 'path': path, 'phase': phase,
            'local_completed': local_completed, 'proposal_ready': ready,
            'proposal_accepted': accepted, 'requires_analysis': stale,
            'confirmed_batch_id': confirmed, 'active_batch_id': active,
            'selected_count': len(effective_selected(service)),
            'target': proposal.get('api_target', settings['target']), 'outcome': outcome}
