"""Semantic policy checks with synthetic vectors and bytes, no downloaded model."""
import copy
import hashlib

import pytest

from lrc_selection.semantic import build_semantic_proposal
from lrc_selection.store import Store


class Encoder:
    identity = {'adapter': 'synthetic-semantic-v1'}
    def __init__(self):
        self.image_calls, self.text_calls = [], []
    def encode(self, path):
        name = path.read_bytes().decode()
        self.image_calls.append(name)
        return {'bird': [1., 0., 0.], 'bird2': [.99, .01, 0.],
                'person': [0., 1., 0.], 'snow': [0., 0., 1.]}[name]
    def encode_text(self, text):
        self.text_calls.append(text)
        return {'uccelli': [1., 0., 0.], 'persone': [0., 1., 0.]}[text]


def fixture(tmp_path):
    store = Store(tmp_path)
    (tmp_path / 'previews').mkdir()
    photos = []
    for index, name in enumerate(['bird', 'bird2', 'person', 'snow']):
        data = name.encode()
        pid = str(index)
        store.preview_path('synthetic', pid).write_bytes(data)
        photos.append({'id': pid, 'preview_ready': True, 'preview_sha256': hashlib.sha256(data).hexdigest()})
    snapshot = {'id': 'synthetic', 'photos': photos, 'settings': {'target': 2, 'subject_query': 'uccelli'}, 'decisions': {}}
    return store, snapshot, Encoder()


def test_subject_query_retrieval_cache_and_no_mutation(tmp_path):
    store, snapshot, encoder = fixture(tmp_path)
    original = copy.deepcopy(snapshot)
    progress = []
    result = build_semantic_proposal(store, snapshot, encoder, lambda n, total: progress.append((n, total)))
    assert result['shortlist'] == ['0', '1']
    assert result['query_scores']['0'] > result['query_scores']['2']
    assert len(result['shortlist_reasons']) == 2
    assert snapshot == original
    assert progress == [(1, 4), (2, 4), (3, 4), (4, 4)]
    snapshot['settings']['subject_query'] = 'persone'
    result = build_semantic_proposal(store, snapshot, encoder)
    assert result['shortlist'][0] == '2'
    assert len(encoder.image_calls) == 4
    assert encoder.text_calls == ['uccelli', 'persone']
    build_semantic_proposal(store, snapshot, encoder)
    assert encoder.text_calls == ['uccelli', 'persone']


def test_diversity_and_manual_precedence(tmp_path):
    store, snapshot, encoder = fixture(tmp_path)
    snapshot['settings']['subject_query'] = ''
    assert build_semantic_proposal(store, snapshot, encoder)['shortlist'] == ['0', '2']
    snapshot['decisions'] = {'0': {'state': 'excluded', 'locked': True},
                             '1': {'state': 'alternative'},
                             '3': {'state': 'preferred', 'locked': True}}
    result = build_semantic_proposal(store, snapshot, encoder)
    assert result['shortlist'] == ['3', '2']
    snapshot['settings']['target'] = 1
    snapshot['decisions']['2'] = {'state': 'candidate'}
    result = build_semantic_proposal(store, snapshot, encoder)
    assert set(result['shortlist']) == {'2', '3'}
    assert any('decisioni manuali' in warning for warning in result['warnings'])


def test_missing_previews_preserved_and_hash_checked(tmp_path):
    store, snapshot, encoder = fixture(tmp_path)
    snapshot['photos'][0]['preview_ready'] = False
    snapshot['decisions']['0'] = {'state': 'review', 'locked': True}
    result = build_semantic_proposal(store, snapshot, encoder)
    assert result['shortlist'][0] == '0'
    assert result['interpretations']['records']['0']['error'] == 'Anteprima mancante'
    assert '0' not in result['query_scores']
    assert len(encoder.image_calls) == 3
    store.preview_path('synthetic', '1').write_bytes(b'changed')
    with pytest.raises(ValueError, match='Anteprima cambiata'):
        build_semantic_proposal(store, snapshot, encoder)


def test_interruption_reuses_successful_image_cache(tmp_path):
    store, snapshot, encoder = fixture(tmp_path)
    def interrupt(n, total):
        if n == 2:
            raise RuntimeError('synthetic interruption')
    with pytest.raises(RuntimeError):
        build_semantic_proposal(store, snapshot, encoder, interrupt)
    result = build_semantic_proposal(store, snapshot, encoder)
    assert len(encoder.image_calls) == 4
    assert len(result['shortlist']) == 2


def test_invalid_vector_fails_without_pretending_selection(tmp_path):
    store, snapshot, encoder = fixture(tmp_path)
    encoder.encode = lambda path: [float('nan'), 1.]
    with pytest.raises(ValueError):
        build_semantic_proposal(store, snapshot, encoder)


def instruction_result(matches=('0','1','2','3')):
    return {'shortlist':list(matches[:2]),'shortlist_reasons':{},'warnings':[], 'method':{},
            'assessments':{str(i):{'match':'yes' if str(i) in matches else 'no',
                                 'reason':'synthetic visible evidence','preference_score':.5} for i in range(4)},
            'interpretations':{'records':{}}, 'blocked':False}


def test_instruction_diversity_separates_near_duplicate_birds_and_keeps_inputs(tmp_path):
    from lrc_selection.semantic import rerank_instruction_shortlist
    store,snapshot,encoder=fixture(tmp_path)
    result=instruction_result()
    original=copy.deepcopy(result)
    reranked=rerank_instruction_shortlist(result,snapshot,store,encoder)
    assert reranked['shortlist']==['0','2']
    assert result==original
    assert all(a['match']=='yes' for a in reranked['assessments'].values())
    assert reranked['method']['novelty_weight']==.3
    assert 'embedding' in reranked['interpretations']['records']['0']
    rerank_instruction_shortlist(result,snapshot,store,encoder)
    assert len(encoder.image_calls)==4


def test_instruction_diversity_preserves_forced_decisions_and_never_fills(tmp_path):
    from lrc_selection.semantic import rerank_instruction_shortlist
    store,snapshot,encoder=fixture(tmp_path)
    snapshot['decisions']={'3':{'state':'preferred','locked':True},'0':{'state':'excluded','locked':True}}
    result=instruction_result(matches=('0','1','2'))
    reranked=rerank_instruction_shortlist(result,snapshot,store,encoder)
    assert reranked['shortlist']==['3','1']
    snapshot['settings']['target']=4
    result=instruction_result(matches=())
    assert rerank_instruction_shortlist(result,snapshot,store,encoder)['shortlist']==['3']
    snapshot['decisions']={}
    assert rerank_instruction_shortlist(result,snapshot,store,encoder)['shortlist']==[]


def test_instruction_preference_can_outweigh_small_diversity_difference(tmp_path):
    from lrc_selection.semantic import rerank_instruction_shortlist
    store,snapshot,encoder=fixture(tmp_path)
    result=instruction_result()
    result['assessments']['0']['preference_score']=1.
    result['assessments']['1']['preference_score']=.99
    result['assessments']['2']['preference_score']=.1
    result['assessments']['3']['preference_score']=.1
    assert rerank_instruction_shortlist(result,snapshot,store,encoder)['shortlist']==['0','1']
    result['blocked']=True
    encoder.encode=lambda path: pytest.fail('blocked instruction must not encode')
    assert rerank_instruction_shortlist(result,snapshot,store,encoder)==result
