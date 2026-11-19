"""Offline review proposals: distinct visual groups before balanced variants.

Similarity supplies conservative grouping evidence, never certified identities,
poses or scene coverage. Instructions and manual decisions remain authoritative.
"""
import hashlib
import numpy as np

from .engine import SELECTED
from .features import FeatureCache, comparison_suggestions
from .selection import select_with_category_coverage, visual_signature, group_visual_neighbors, SELECTION_POLICY, GROUPING_POLICY

RELEVANCE_WEIGHT = 1.


def _normalized(values):
    vector = np.asarray(values, dtype=np.float32)
    if vector.ndim != 1 or not np.isfinite(vector).all() or np.linalg.norm(vector) <= 0:
        raise ValueError('Embedding semantico non valido')
    return vector / np.linalg.norm(vector)


def build_semantic_proposal(store, snapshot, encoder, progress=None):
    """Return evidence and provisional shortlist; leave all stored decisions intact.

    progress(completed, total) is called after each image (including cache hits).
    Successful image/text embeddings survive interruption through FeatureCache.
    """
    cache = FeatureCache(store.root)
    records, vectors = {}, {}
    photos = snapshot['photos']
    for index, photo in enumerate(photos):
        pid = photo['id']
        if not photo.get('preview_ready'):
            records[pid] = {'error': 'Anteprima mancante'}
        else:
            path = store.preview_path(snapshot['id'], pid)
            raw = path.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            if digest != photo['preview_sha256']:
                raise ValueError('Anteprima cambiata: reimportare prima di analizzare')
            embedding = cache.get_or_compute(digest, 'embedding', encoder.identity, lambda: encoder.encode(path))
            vectors[pid] = _normalized(embedding)
            records[pid] = {'preview_sha256': digest, 'embedding': vectors[pid].tolist(), 'visual_signature': visual_signature(raw)}
        if progress:
            progress(index + 1, len(photos))

    decisions = snapshot.get('decisions', {})
    eligible = [p['id'] for p in photos if decisions.get(p['id'], {}).get('state') not in {'excluded', 'alternative'}]
    shortlist = [pid for pid in eligible if decisions.get(pid, {}).get('state') in SELECTED]
    query = snapshot['settings'].get('subject_query', '').strip()
    scores = {}
    if query:
        key = hashlib.sha256(query.encode('utf-8')).hexdigest()
        text = _normalized(cache.get_or_compute(key, 'subject-text', encoder.identity, lambda: encoder.encode_text(query)))
        for pid, vector in vectors.items():
            if vector.shape != text.shape:
                raise ValueError('Dimensioni degli embedding incompatibili')
            scores[pid] = float(np.clip(np.dot(vector, text), -1, 1))
    if vectors and len({v.shape for v in vectors.values()}) != 1:
        raise ValueError('Dimensioni degli embedding incompatibili')

    target = snapshot['settings']['target']
    remaining = [pid for pid in eligible if pid in vectors and pid not in shortlist]
    remaining.sort(key=lambda pid: -scores.get(pid, 0.))
    shortlist.extend(remaining)

    forced = [pid for pid in eligible if decisions.get(pid, {}).get('state') in SELECTED]
    groups = group_visual_neighbors(shortlist, {pid: record.get('visual_signature') for pid, record in records.items()}, vectors)
    balanced = select_with_category_coverage([pid for pid in shortlist if pid not in forced], forced,
                  {pid: {'match': 'yes'} for pid in vectors}, [], target, groups)
    shortlist = balanced['shortlist']
    review_ids = [pid for pid in eligible if pid not in vectors]
    shortlist.extend(pid for pid in review_ids if pid not in shortlist)

    warnings = ['Proposta da rivedere: somiglianza visiva e pertinenza al soggetto non dimostrano equivalenza, identità o copertura delle situazioni.']
    if len(forced) > target:
        warnings.append('Le decisioni manuali richiedono più immagini della quantità indicata: tutte conservate.')
    elif len(shortlist) < target:
        warnings.append('Quantità non raggiunta: alternative/esclusioni manuali o anteprime mancanti limitano la proposta.')
    if any('error' in record for record in records.values()):
        warnings.append('Anteprime mancanti: le immagini restano candidate e richiedono revisione manuale.')
    reasons = {}
    for pid in shortlist:
        if pid in review_ids:
            reasons[pid] = 'Anteprima mancante o non valutabile: conservata da rivedere, nessuna esclusione automatica.'
        elif decisions.get(pid, {}).get('state') in SELECTED:
            reasons[pid] = 'Inclusa per decisione manuale, preservata durante l’analisi.'
        elif query:
            reasons[pid] = f'Pertinenza visiva al soggetto «{query}» (coseno {scores[pid]:.3f}); diversità visiva considerata nella proposta.'
        else:
            reasons[pid] = 'Inclusa nella proposta per distribuire la diversità degli embedding visivi; situazione reale non identificata.'
    for pid in vectors:
        if pid not in shortlist and pid in eligible:
            reasons[pid] = 'Alternativa dello stesso gruppo visivo: disponibile dopo le rappresentanti degli altri gruppi.'
    warnings.extend(balanced['warnings'])
    warning = warnings[0]
    return {
        'interpretations': {'schema_version': 1, 'model': encoder.identity, 'records': records,
                            'comparisons': comparison_suggestions(records), 'warning': warning},
        'shortlist': shortlist, 'review_ids': review_ids, 'shortlist_reasons': reasons, 'query_scores': scores,
        'model': encoder.identity, 'query': query, 'warnings': warnings,
        'selection_groups': balanced['selection_groups'], 'selection_policy': SELECTION_POLICY,
        'method': {'name': 'semantic-review-v2-groups', 'selection_policy': SELECTION_POLICY, 'grouping': GROUPING_POLICY, 'relevance_weight': RELEVANCE_WEIGHT,
                   'calibrated': False, 'changes_candidate_decisions': False},
    }


def rerank_instruction_shortlist(result, snapshot, store, encoder):
    """Preserve distinct groups before balanced extras, ranked by user merit.

    Conservative visual descriptors plus embeddings identify near variants;
    uncertain photos remain independently preserved by the local review policy.
    """
    from copy import deepcopy
    updated = deepcopy(result)
    if result.get('blocked'):
        return updated
    decisions = snapshot.get('decisions', {})
    assessments = result.get('assessments', {})
    local_policy = result.get('method', {}).get('uncertainty_policy') == LOCAL_UNCERTAINTY_POLICY
    local_review = set(retain_local_review_candidates([], snapshot, assessments)['review_ids']) if local_policy else set()
    eligible = [p for p in snapshot['photos']
                if decisions.get(p['id'], {}).get('state') not in {'excluded', 'alternative'}]
    forced = [p['id'] for p in eligible if decisions.get(p['id'], {}).get('state') in SELECTED and p['id'] not in local_review]
    matches = [p['id'] for p in eligible if assessments.get(p['id'], {}).get('match') == 'yes'
               and p['id'] not in forced and p['id'] not in local_review]
    vectors = {}
    cache = FeatureCache(store.root)
    needed = set(forced + matches)
    for photo in eligible:
        pid = photo['id']
        if pid not in needed or not photo.get('preview_ready'):
            continue
        path = store.preview_path(snapshot['id'], pid)
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != photo['preview_sha256']:
            raise ValueError('Anteprima cambiata: reimportare prima di analizzare')
        vector = _normalized(cache.get_or_compute(digest, 'embedding', encoder.identity,
                                                  lambda: encoder.encode(path)))
        vectors[pid] = vector
        records = updated.setdefault('interpretations', {}).setdefault('records', {})
        records.setdefault(pid, {'preview_sha256': digest})['embedding'] = vector.tolist()
        records[pid]['visual_signature'] = visual_signature(raw)
    if vectors and len({v.shape for v in vectors.values()}) != 1:
        raise ValueError('Dimensioni degli embedding incompatibili')
    for pid in matches:
        preference = assessments[pid].get('preference_score', .5)
        if not isinstance(preference, (int, float)) or not np.isfinite(preference) or not 0 <= preference <= 1:
            raise ValueError('Punteggio di preferenza non valido')
    ordered = sorted((pid for pid in matches if pid in vectors),
                     key=lambda pid: -assessments[pid].get('preference_score', .5))
    selected = forced + ordered
    ranking_evidence = {pid: {'preference_score': assessments[pid].get('preference_score', .5)} for pid in ordered}
    categories = result.get('instruction_interpretation', {}).get('requested_categories', [])
    coverage_assessments = local_confirmed_coverage_assessments(assessments) if local_policy else assessments
    records = updated.get('interpretations', {}).get('records', {})
    groups = group_visual_neighbors(selected, {pid: record.get('visual_signature') for pid, record in records.items()}, vectors)
    covered = select_with_category_coverage([pid for pid in selected if pid not in forced], forced,
                                             coverage_assessments, categories, snapshot['settings']['target'], groups)
    selected = covered['shortlist']
    if local_policy:
        retained = retain_local_review_candidates(selected, snapshot, assessments)
        selected = retained['shortlist']
        updated['review_ids'] = retained['review_ids']
        updated.setdefault('warnings', []).extend(w for w in retained['warnings'] if w not in updated.get('warnings', []))
    updated['shortlist'] = selected
    updated['coverage'] = covered['coverage']
    updated['selection_groups'] = covered['selection_groups']
    updated['selection_policy'] = SELECTION_POLICY
    updated.setdefault('warnings', []).extend(w for w in covered['warnings'] if w not in updated.get('warnings', []))
    reasons = {}
    for pid in dict.fromkeys(selected + matches):
        if pid not in selected:
            reasons[pid] = assessments[pid]['reason'] + ' Alternativa dello stesso gruppo: priorità alle rappresentanti degli altri gruppi prima delle varianti aggiuntive.'
        elif pid in local_review:
            reasons[pid] = result.get('shortlist_reasons', {}).get(pid, 'Da rivedere, conservata per prudenza: ' + assessments.get(pid, {}).get('reason', 'Valutazione non disponibile.'))
        elif pid in forced:
            reasons[pid] = 'Decisione manuale preservata.'
        else:
            reasons[pid] = assessments[pid]['reason'] + ' Diversità visiva considerata nella proposta (confronto di embedding, equivalenza non dimostrata).'
    updated['shortlist_reasons'] = reasons
    updated['diversity_model'] = encoder.identity
    updated['ranking_evidence'] = ranking_evidence
    updated.setdefault('method', {}).update(
        ranking=SELECTION_POLICY, grouping=GROUPING_POLICY,
        preference_weight=1., novelty_weight=0., calibrated=False)
    updated['warnings'] = [w for w in updated.get('warnings', []) if not w.startswith('Diversità visiva stimata dagli embedding con pesi sperimentali')]
    warning = 'Prima una rappresentante per ogni gruppo visivo distinto, poi varianti aggiuntive a turni bilanciati; preferenze e merito fotografico ordinano le immagini nello stesso gruppo. Gruppi da verificare, nessuna identità o copertura certificata.'
    if warning not in updated.setdefault('warnings', []):
        updated['warnings'].append(warning)
    if any(pid not in vectors for pid in matches):
        updated['warnings'].append('Corrispondenze senza anteprima disponibili: da rivedere, non aggiunte automaticamente alla proposta.')
    return updated




LOCAL_UNCERTAINTY_POLICY = 'retain-uncertain-v1'


def local_confirmed_coverage_assessments(assessments):
    """Unknown/error photos remain review candidates, never confirmed coverage.

    This local-only view leaves original model assessments unchanged and does not
    change the shared API category selector's behavior.
    """
    result = {}
    for pid, assessment in assessments.items():
        if assessment.get('match') != 'yes' or assessment.get('error'):
            result[pid] = dict(assessment, category_matches={
                cid: 'uncertain' if match == 'yes' else match
                for cid, match in assessment.get('category_matches', {}).items()})
        else:
            result[pid] = assessment
    return result


def retain_local_review_candidates(shortlist, snapshot, assessments):
    """Append every eligible unknown after the normal confirmed proposal.

    These additions do not fill the confirmed target or establish category
    coverage. Explicit manual exclusions/alternatives always prevail.
    """
    photos = {photo['id']: photo for photo in snapshot['photos']}
    eligible = [pid for pid in photos
                if snapshot.get('decisions', {}).get(pid, {}).get('state') not in {'excluded', 'alternative'}]
    eligible_set = set(eligible)
    selected = list(dict.fromkeys(pid for pid in shortlist if pid in eligible_set))
    review_ids = [pid for pid in eligible if photos[pid].get('preview_ready') is False or not assessments.get(pid)
                  or assessments[pid].get('match') == 'uncertain' or assessments[pid].get('error')]
    selected.extend(pid for pid in review_ids if pid not in selected)
    warnings = []
    if review_ids:
        warnings.append(f'{len(review_ids)} immagini incerte o non valutabili conservate nella proposta come da rivedere; non sono corrispondenze confermate.')
        if len(selected) > snapshot['settings']['target']:
            warnings.append('Quantità indicativa superata per conservare tutte le immagini da rivedere, oltre alle candidate confermate.')
    return {'shortlist': selected, 'review_ids': review_ids, 'warnings': warnings}
