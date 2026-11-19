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

    Experimental MMR: 0.7 * ordinal user preference/photographic merit +
    0.3 * embedding novelty.
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
    categories = result.get('instruction_interpretation', {}).get('requested_categories', [])
    while remaining and (categories or len(selected) < snapshot['settings']['target']):
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
    coverage_assessments = local_confirmed_coverage_assessments(assessments) if local_policy else assessments
    covered = select_with_category_coverage([pid for pid in selected if pid not in forced], forced,
                                             coverage_assessments, categories, snapshot['settings']['target'])
    selected = covered['shortlist']
    if local_policy:
        retained = retain_local_review_candidates(selected, snapshot, assessments)
        selected = retained['shortlist']
        updated['review_ids'] = retained['review_ids']
        updated.setdefault('warnings', []).extend(w for w in retained['warnings'] if w not in updated.get('warnings', []))
    updated['shortlist'] = selected
    updated['coverage'] = covered['coverage']
    updated.setdefault('warnings', []).extend(w for w in covered['warnings'] if w not in updated.get('warnings', []))
    reasons = {}
    for pid in selected:
        if pid in local_review:
            reasons[pid] = result.get('shortlist_reasons', {}).get(pid, 'Da rivedere, conservata per prudenza: ' + assessments.get(pid, {}).get('reason', 'Valutazione non disponibile.'))
        elif pid in forced:
            reasons[pid] = 'Decisione manuale preservata.'
        else:
            reasons[pid] = assessments[pid]['reason'] + ' Diversità visiva considerata nella proposta (confronto di embedding, equivalenza non dimostrata).'
    updated['shortlist_reasons'] = reasons
    updated['diversity_model'] = encoder.identity
    updated['ranking_evidence'] = ranking_evidence
    updated.setdefault('method', {}).update(
        ranking='instruction-preference-and-visual-diversity-v1',
        preference_weight=.7, novelty_weight=.3, calibrated=False)
    warning = 'Diversità visiva stimata dagli embedding con pesi sperimentali 70% preferenze e merito fotografico e 30% novità; non certifica scene, persone o copertura.'
    if warning not in updated.setdefault('warnings', []):
        updated['warnings'].append(warning)
    if any(pid not in vectors for pid in matches):
        updated['warnings'].append('Corrispondenze senza anteprima disponibili: da rivedere, non aggiunte automaticamente alla proposta.')
    return updated


def select_with_category_coverage(ordered_ids, forced_ids, assessments, categories, target):
    """Represent every requested category with eligible positive model evidence.

    Input order is the caller's preference/diversity ranking. Never use uncertain
    or negative evidence as a substitute. The requested quantity is a target:
    category coverage and manual positives may exceed it, with an explicit warning.
    This preserves only categories the model reported, not all real situations.
    """
    selected = list(dict.fromkeys(forced_ids))
    ordered = list(dict.fromkeys(pid for pid in ordered_ids if pid not in selected))
    category_ids = [category['id'] for category in categories]
    def covers(pid, category_id):
        return assessments.get(pid, {}).get('category_matches', {}).get(category_id) == 'yes'
    uncovered = {cid for cid in category_ids if not any(covers(pid, cid) for pid in selected)}
    while uncovered:
        candidates = [pid for pid in ordered if assessments.get(pid, {}).get('match') == 'yes'
                      and any(covers(pid, cid) for cid in uncovered)]
        if not candidates:
            break
        chosen = max(candidates, key=lambda pid: sum(covers(pid, cid) for cid in uncovered))
        selected.append(chosen)
        ordered.remove(chosen)
        uncovered = {cid for cid in uncovered if not covers(chosen, cid)}
    for pid in ordered:
        if len(selected) >= target:
            break
        if assessments.get(pid, {}).get('match') == 'yes':
            selected.append(pid)
    coverage, warnings = [], []
    eligible = set(ordered_ids) | set(forced_ids)
    for category in categories:
        cid, description = category['id'], category['description']
        representatives = [pid for pid in selected if covers(pid, cid)]
        recognized = [pid for pid, a in assessments.items() if a.get('match') == 'yes' and covers(pid, cid)]
        available = [pid for pid in recognized if pid in eligible]
        uncertain = [pid for pid, a in assessments.items()
                     if a.get('category_matches', {}).get(cid, 'uncertain') == 'uncertain']
        if representatives:
            status = 'represented'
        elif recognized and not available:
            status = 'manual-excluded'
            warnings.append(f'Categoria richiesta «{description}» non rappresentata: le corrispondenze sono escluse dalle decisioni manuali.')
        elif not assessments:
            status = 'not-assessed'
            warnings.append(f'Categoria richiesta «{description}» non valutata: analisi non eseguita.')
        elif uncertain:
            status = 'uncertain'
            warnings.append(f'Categoria richiesta «{description}» non confermata: presenti valutazioni incerte da rivedere, nessuna sostituzione automatica.')
        else:
            status = 'not-detected'
            warnings.append(f'Categoria richiesta «{description}»: nessuna corrispondenza idonea rilevata; non è prova di assenza nel servizio.')
        coverage.append({'id': cid, 'description': description, 'selected_ids': representatives,
                         'eligible_count': len(available), 'uncertain_count': len(uncertain), 'status': status})
    if len(selected) > target:
        warnings.append('Quantità indicativa superata per preservare categorie richieste e decisioni manuali: rivedere il compromesso prima di confermare.')
    return {'shortlist': selected, 'coverage': coverage, 'warnings': warnings}


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
