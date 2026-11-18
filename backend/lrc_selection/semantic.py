"""Offline, review-only retrieval from imported previews.

The shortlist is not an equivalence claim or an exclusion decision. MMR uses a
fixed experimental relevance weight (0.85), exposed in the result, not a calibrated
photographic quality threshold. Image similarity cannot establish people/poses.
"""
import hashlib
import numpy as np

from .engine import SELECTED
from .features import FeatureCache, comparison_suggestions

RELEVANCE_WEIGHT = .85


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
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != photo['preview_sha256']:
                raise ValueError('Anteprima cambiata: reimportare prima di analizzare')
            embedding = cache.get_or_compute(digest, 'embedding', encoder.identity, lambda: encoder.encode(path))
            vectors[pid] = _normalized(embedding)
            records[pid] = {'preview_sha256': digest, 'embedding': vectors[pid].tolist()}
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
    while remaining and len(shortlist) < target:
        selected_vectors = [vectors[pid] for pid in shortlist if pid in vectors]
        def priority(pid):
            redundancy = max((float(np.dot(vectors[pid], other)) for other in selected_vectors), default=0.)
            if query:
                return RELEVANCE_WEIGHT * scores[pid] - (1 - RELEVANCE_WEIGHT) * redundancy
            # Stable first image seeds the spread when no subject was specified.
            return -redundancy if selected_vectors else 0.
        chosen = max(remaining, key=priority)  # ties retain original import order
        shortlist.append(chosen)
        remaining.remove(chosen)

    warnings = ['Proposta da rivedere: somiglianza visiva e pertinenza al soggetto non dimostrano equivalenza, identità o copertura delle situazioni.']
    if len(shortlist) > target:
        warnings.append('Le decisioni manuali richiedono più immagini della quantità indicata: tutte conservate.')
    elif len(shortlist) < target:
        warnings.append('Quantità non raggiunta: alternative/esclusioni manuali o anteprime mancanti limitano la proposta.')
    if any('error' in record for record in records.values()):
        warnings.append('Anteprime mancanti: le immagini restano candidate e richiedono revisione manuale.')
    reasons = {}
    for pid in shortlist:
        if decisions.get(pid, {}).get('state') in SELECTED:
            reasons[pid] = 'Inclusa per decisione manuale, preservata durante l’analisi.'
        elif query:
            reasons[pid] = f'Pertinenza visiva al soggetto «{query}» (coseno {scores[pid]:.3f}); diversità visiva considerata nella proposta.'
        else:
            reasons[pid] = 'Inclusa nella proposta per distribuire la diversità degli embedding visivi; situazione reale non identificata.'
    warning = warnings[0]
    return {
        'interpretations': {'schema_version': 1, 'model': encoder.identity, 'records': records,
                            'comparisons': comparison_suggestions(records), 'warning': warning},
        'shortlist': shortlist, 'shortlist_reasons': reasons, 'query_scores': scores,
        'model': encoder.identity, 'query': query, 'warnings': warnings,
        'method': {'name': 'semantic-review-v1', 'relevance_weight': RELEVANCE_WEIGHT,
                   'calibrated': False, 'changes_candidate_decisions': False},
    }


def rerank_instruction_shortlist(result, snapshot, store, encoder):
    """Add visual diversity among confirmed matches without changing assessments.

    Experimental MMR: 0.7 * model ordinal preference + 0.3 * embedding novelty.
    Novelty is (1 - highest cosine similarity to an already selected image) / 2.
    The constants are exposed, not calibrated. This list does not establish
    equivalence, person identities or scene coverage. No missing/uncertain/no
    assessment is used to fill the requested count.
    """
    from copy import deepcopy
    updated = deepcopy(result)
    if result.get('blocked'):
        return updated
    decisions = snapshot.get('decisions', {})
    assessments = result.get('assessments', {})
    eligible = [p for p in snapshot['photos']
                if decisions.get(p['id'], {}).get('state') not in {'excluded', 'alternative'}]
    forced = [p['id'] for p in eligible if decisions.get(p['id'], {}).get('state') in SELECTED]
    matches = [p['id'] for p in eligible if assessments.get(p['id'], {}).get('match') == 'yes'
               and p['id'] not in forced]
    vectors = {}
    cache = FeatureCache(store.root)
    needed = set(forced + matches)
    for photo in eligible:
        pid = photo['id']
        if pid not in needed or not photo.get('preview_ready'):
            continue
        path = store.preview_path(snapshot['id'], pid)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != photo['preview_sha256']:
            raise ValueError('Anteprima cambiata: reimportare prima di analizzare')
        vector = _normalized(cache.get_or_compute(digest, 'embedding', encoder.identity,
                                                  lambda: encoder.encode(path)))
        vectors[pid] = vector
        records = updated.setdefault('interpretations', {}).setdefault('records', {})
        records.setdefault(pid, {'preview_sha256': digest})['embedding'] = vector.tolist()
    if vectors and len({v.shape for v in vectors.values()}) != 1:
        raise ValueError('Dimensioni degli embedding incompatibili')
    selected = list(forced)
    remaining = [pid for pid in matches if pid in vectors]
    ranking_evidence = {}
    while remaining and len(selected) < snapshot['settings']['target']:
        selected_vectors = [vectors[pid] for pid in selected if pid in vectors]
        evaluated = {}
        for pid in remaining:
            preference = assessments[pid].get('preference_score', .5)
            if not isinstance(preference, (int, float)) or not np.isfinite(preference) or not 0 <= preference <= 1:
                raise ValueError('Punteggio di preferenza non valido')
            similarity = max((float(np.clip(np.dot(vectors[pid], vector), -1, 1))
                              for vector in selected_vectors), default=0.)
            novelty = (1 - similarity) / 2
            evaluated[pid] = {'preference_score': preference, 'novelty': novelty,
                              'rank_score': .7 * preference + .3 * novelty}
        chosen = max(remaining, key=lambda pid: evaluated[pid]['rank_score'])
        selected.append(chosen)
        remaining.remove(chosen)
        ranking_evidence[chosen] = evaluated[chosen]
    updated['shortlist'] = selected
    reasons = {}
    for pid in selected:
        if pid in forced:
            reasons[pid] = 'Decisione manuale preservata.'
        else:
            reasons[pid] = assessments[pid]['reason'] + ' Diversità visiva considerata nella proposta (confronto di embedding, equivalenza non dimostrata).'
    updated['shortlist_reasons'] = reasons
    updated['diversity_model'] = encoder.identity
    updated['ranking_evidence'] = ranking_evidence
    updated.setdefault('method', {}).update(
        ranking='instruction-preference-and-visual-diversity-v1',
        preference_weight=.7, novelty_weight=.3, calibrated=False)
    warning = 'Diversità visiva stimata dagli embedding con pesi sperimentali 70% preferenze e 30% novità; non certifica scene, persone o copertura.'
    if warning not in updated.setdefault('warnings', []):
        updated['warnings'].append(warning)
    if any(pid not in vectors for pid in matches):
        updated['warnings'].append('Corrispondenze senza anteprima disponibili: da rivedere, non aggiunte automaticamente alla proposta.')
    return updated
