"""Conservative baseline: only byte-identical derived previews are equivalent.

No claim of scene/person recognition. Without calibrated evidence, every distinct
preview is kept. Optional embedding extraction is separate from selection policy.
"""
from collections import defaultdict

SELECTED = {'candidate', 'preferred', 'review'}

def effective_selected(service):
    selected = set(service['proposal']['selected']) if service.get('proposal') else {p['id'] for p in service['photos']}
    if service.get('proposal'):
        selected.update(service['proposal'].get('added_candidates', ()))
    for pid, decision in service['decisions'].items():
        if decision['state'] in SELECTED:
            selected.add(pid)
        else:
            selected.discard(pid)
    return [p['id'] for p in service['photos'] if p['id'] in selected]

def effective_shortlist(service):
    """Review proposal with explicit manual choices taking precedence."""
    proposal = service.get('proposal') or {}
    selected = set(proposal.get('shortlist', []))
    for pid, decision in service.get('decisions', {}).items():
        if decision['state'] in SELECTED:
            selected.add(pid)
        else:
            selected.discard(pid)
    return [photo['id'] for photo in service['photos'] if photo['id'] in selected]


def analyze(service):
    buckets = defaultdict(list)
    for photo in service['photos']:
        # Missing previews must never become evidence for equivalence.
        key = photo.get('preview_sha256') or ('missing:' + photo['id'])
        buckets[key].append(photo['id'])
    groups, selected, reasons = [], [], {}
    for i, members in enumerate(buckets.values()):
        positive = [p for p in members if service['decisions'].get(p, {}).get('state') in SELECTED]
        allowed = [p for p in members if service['decisions'].get(p, {}).get('state') not in {'excluded', 'alternative'}]
        rep = (positive or allowed or members)[0]
        reason = ('Anteprime JPEG identiche byte per byte; equivalenza del contenuto visibile, non degli originali.'
                  if len(members) > 1 else 'Nessuna equivalenza dimostrata: immagine conservata.')
        groups.append({'id': f'exact-{i}', 'members': members, 'representative': rep, 'reason': reason,
                       'kind': 'preview-equivalence', 'confidence': 'exact-preview' if len(members) > 1 else 'unknown'})
        if allowed:
            selected.append(rep)
        for pid in members:
            reasons[pid] = reason
    target = service['settings']['target']
    for p in service['photos']:
        if len(selected) >= target:
            break
        if p['id'] not in selected and service['decisions'].get(p['id'], {}).get('state') not in {'excluded', 'alternative'}:
            selected.append(p['id'])
            reasons[p['id']] = 'Recuperata tra le alternative per raggiungere la quantità richiesta.'
    proposal = {'selected': selected, 'groups': groups, 'reasons': reasons,
                'warnings': ['Il motore iniziale riconosce solo anteprime identiche; scene, persone e pose non sono state riconosciute.'],
                'engine': 'exact-preview-v1'}
    working = dict(service, proposal=proposal)
    proposal['selected'] = effective_selected(working)
    if len(proposal['selected']) < target:
        proposal['warnings'].append('Quantità non raggiungibile senza cambiare decisioni manuali: revisione necessaria.')
    if len(proposal['selected']) > target:
        proposal['warnings'].append('Quantità superata: mancano evidenze sufficienti per ridurre altre immagini in sicurezza.')
    for g in groups:
        if not set(g['members']) & set(proposal['selected']):
            proposal['warnings'].append('Un gruppo non ha candidate per effetto delle decisioni manuali.')
    return proposal
