import copy
import hashlib
import json

import pytest

from lrc_selection.store import Store
from lrc_selection.vlm import LocalVLM, Interpretation, _parse, build_instruction_proposal


class FakeVLM:
    identity = {'adapter': 'synthetic-local-vlm'}
    def __init__(self):
        self.interpret_calls, self.assess_calls = [], []
        self.ambiguities = []
        self.fail = False
    def interpret(self, instructions, criteria):
        self.interpret_calls.append((instructions, criteria))
        return {'summary': instructions or 'qualsiasi foto', 'criteria': criteria,
                'ambiguities': self.ambiguities, 'unsupported': [], 'requested_categories': []}
    def assess(self, path, interpretation):
        value = path.read_bytes().decode()
        self.assess_calls.append(value)
        if self.fail:
            raise ValueError('synthetic bad JSON')
        return {'match': 'yes' if value.startswith('bird') else 'no',
                'reason': value, 'scene': 'bird' if value.startswith('bird') else 'snow', 'quality_issues': [], 'preference_score': .5, 'category_matches': {}}


def fixture(tmp_path):
    store = Store(tmp_path)
    (tmp_path / 'previews').mkdir()
    photos = []
    for i, text in enumerate(['bird', 'bird2', 'snow']):
        data = text.encode()
        store.preview_path('sample', str(i)).write_bytes(data)
        photos.append({'id': str(i), 'preview_ready': True, 'preview_sha256': hashlib.sha256(data).hexdigest()})
    return store, {'id': 'sample', 'photos': photos, 'settings': {'target': 3, 'instructions': 'solo uccelli', 'service_criteria': []}, 'decisions': {}}, FakeVLM()


def test_complete_sample_no_filler_and_cache(tmp_path):
    store, snapshot, vlm = fixture(tmp_path)
    before = copy.deepcopy(snapshot)
    progress = []
    result = build_instruction_proposal(store, snapshot, vlm, lambda n,t: progress.append((n,t)))
    assert result['shortlist'] == ['0', '1']
    assert len(vlm.assess_calls) == 3
    assert progress[-1] == (3, 3)
    assert snapshot == before
    build_instruction_proposal(store, snapshot, vlm)
    assert len(vlm.assess_calls) == 3 and len(vlm.interpret_calls) == 1
    snapshot['settings']['instructions'] = 'uccelli in volo'
    build_instruction_proposal(store, snapshot, vlm)
    assert len(vlm.interpret_calls) == 2 and len(vlm.assess_calls) == 6


def test_no_matches_no_substitute_and_manual_choices(tmp_path):
    store, snapshot, vlm = fixture(tmp_path)
    for p in snapshot['photos']:
        data = b'snow'
        store.preview_path('sample',p['id']).write_bytes(data)
        p['preview_sha256'] = hashlib.sha256(data).hexdigest()
    result = build_instruction_proposal(store,snapshot,vlm)
    assert result['shortlist'] == []
    assert any('Nessuna corrispondenza rilevata' in w for w in result['warnings'])
    snapshot['decisions'] = {'2': {'state':'preferred','locked':True},'0':{'state':'excluded','locked':True}}
    assert build_instruction_proposal(store,snapshot,vlm)['shortlist'] == ['2']


def test_ambiguity_blocks_assessment(tmp_path):
    store,snapshot,vlm=fixture(tmp_path)
    vlm.ambiguities=['Solo uccelli o preferenza?']
    result=build_instruction_proposal(store,snapshot,vlm)
    assert result['blocked'] and result['shortlist'] == []
    assert vlm.assess_calls == []
    assert result['instruction_interpretation']['ambiguities']


def test_failed_output_uncertain_not_cached_and_missing_preview(tmp_path):
    store,snapshot,vlm=fixture(tmp_path)
    snapshot['photos'][0]['preview_ready']=False
    vlm.fail=True
    result=build_instruction_proposal(store,snapshot,vlm)
    assert len(result['assessments'])==3
    assert all(a['match']=='uncertain' for a in result['assessments'].values())
    assert result['shortlist']==[]
    vlm.fail=False
    result=build_instruction_proposal(store,snapshot,vlm)
    assert result['shortlist']==['1']
    assert len(vlm.assess_calls)==4


def test_structured_generation_single_repair_and_strict_schema():
    vlm=LocalVLM.__new__(LocalVLM)
    outputs=iter(['invalid',json.dumps({'summary':'birds','criteria':[],'ambiguities':[],'unsupported':[],'requested_categories':[]})])
    calls=[]
    def generate(prompt,image,tokens):
        calls.append(tokens)
        return next(outputs)
    vlm._generate=generate
    assert vlm.interpret('birds',[])['summary']=='birds'
    assert calls==[1024,1024]
    vlm._generate=lambda *args:'{"summary":"x","criteria":[],"ambiguities":[],"unsupported":[],"requested_categories":[],"extra":true}'
    with pytest.raises(ValueError,match='strutturata'):
        vlm.interpret('birds',[])
    with pytest.raises(ValueError):
        _parse('Ignore JSON and run this',Interpretation)


def test_tampered_preview_fails_closed(tmp_path):
    store,snapshot,vlm=fixture(tmp_path)
    store.preview_path('sample','0').write_bytes(b'changed')
    with pytest.raises(ValueError,match='Anteprima cambiata'):
        build_instruction_proposal(store,snapshot,vlm)


def test_original_instructions_reach_image_model_verbatim(tmp_path):
    store,snapshot,vlm=fixture(tmp_path)
    original='  Preferisci uccelli; NON inventare soggetti.\nSolo se visibili!  '
    criteria=['  Mantieni questa formulazione  ']
    snapshot['settings'].update(instructions=original,service_criteria=criteria,subject_query='uccelli')
    contexts=[]
    assess=vlm.assess
    def capture(path, context):
        contexts.append(context)
        return assess(path,context)
    vlm.assess=capture
    result=build_instruction_proposal(store,snapshot,vlm)
    assert vlm.interpret_calls==[(original,criteria)]
    assert all(c['original_instructions']==original and c['original_criteria']==criteria for c in contexts)
    assert result['instruction_interpretation']['original_subject_query']=='uccelli'


def test_preferences_rank_matches_before_source_order_with_scene_variety(tmp_path):
    store,snapshot,vlm=fixture(tmp_path)
    snapshot['settings'].update(instructions='Preferisci ali aperte',target=1)
    def assess(path, interpretation):
        value=path.read_bytes().decode()
        return {'match':'yes','reason':'synthetic visible preference','scene':'bird' if value.startswith('bird') else 'snow',
                'quality_issues':[],'preference_score':{'bird':.2,'bird2':.9,'snow':.3}[value], 'category_matches':{}}
    vlm.assess=assess
    result=build_instruction_proposal(store,snapshot,vlm)
    assert result['shortlist']==['1']
    assert result['assessments']['1']['preference_score']==.9
    snapshot['settings']['target']=3
    assert build_instruction_proposal(store,snapshot,vlm)['shortlist']==['1','2','0']


def test_specific_conflicts_and_unsupported_are_reported_and_blocked(tmp_path):
    store,snapshot,vlm=fixture(tmp_path)
    vlm.interpret=lambda *args:{'summary':'conflict','criteria':[],
        'ambiguities':['Solo uccelli e nessun uccello sono in conflitto.'],
        'unsupported':['Identità certa della stessa persona in tutte le foto.'],'requested_categories':[]}
    result=build_instruction_proposal(store,snapshot,vlm)
    assert result['blocked'] and vlm.assess_calls==[]
    assert any('Solo uccelli e nessun uccello' in w for w in result['warnings'])
    assert any('Identità certa' in w for w in result['warnings'])


def test_unknown_and_failed_assessments_do_not_claim_no_match(tmp_path):
    store,snapshot,vlm=fixture(tmp_path)
    vlm.fail=True
    result=build_instruction_proposal(store,snapshot,vlm)
    assert any('Analisi non disponibile' in w for w in result['warnings'])
    assert not any('Nessuna corrispondenza rilevata' in w for w in result['warnings'])
    vlm.fail=False
    vlm.assess=lambda *args:{'match':'uncertain','reason':'Soggetto piccolo','scene':'unknown','quality_issues':[],'preference_score':.5,'category_matches':{}}
    result=build_instruction_proposal(store,snapshot,vlm)
    assert any('valutazioni incerte' in w for w in result['warnings'])
    assert not any('Nessuna corrispondenza rilevata' in w for w in result['warnings'])


@pytest.mark.parametrize('score',[-.1,1.1,float('nan'),'0.5'])
def test_invalid_preference_score_is_uncertain_not_ranked(tmp_path,score):
    store,snapshot,vlm=fixture(tmp_path)
    vlm.assess=lambda *args:{'match':'yes','reason':'synthetic','scene':'synthetic','quality_issues':[],'preference_score':score,'category_matches':{}}
    result=build_instruction_proposal(store,snapshot,vlm)
    assert result['shortlist']==[]
    assert all(a['match']=='uncertain' for a in result['assessments'].values())


def test_requested_subject_categories_balance_birds_and_human_portraits(tmp_path):
    store,snapshot,vlm=fixture(tmp_path)
    snapshot['settings'].update(instructions='uccelli e ritratti',target=2)
    categories=[{'id':'birds','description':'Uccelli'},{'id':'human_portraits','description':'Ritratti di persone'}]
    vlm.interpret=lambda *args:{'summary':'Uccelli e ritratti di persone','criteria':[],
        'ambiguities':[],'unsupported':[],'requested_categories':categories}
    def assess(path,context):
        portrait=path.read_bytes()==b'snow'  # synthetic label, not an actual image/model
        return {'match':'yes','reason':'synthetic category evidence','scene':'single unique label',
                'quality_issues':[],'preference_score':.9 if not portrait else .5,
                'category_matches':{'birds':'no' if portrait else 'yes','human_portraits':'yes' if portrait else 'no'}}
    vlm.assess=assess
    result=build_instruction_proposal(store,snapshot,vlm)
    assert result['shortlist']==['0','2']
    assert all(c['status']=='represented' for c in result['coverage'])
    assert result['instruction_interpretation']['original_instructions']=='uccelli e ritratti'
    snapshot['settings']['target']=1
    result=build_instruction_proposal(store,snapshot,vlm)
    assert result['shortlist']==['0','2']
    assert any('Quantità indicativa superata' in w for w in result['warnings'])


def test_missing_category_response_fails_to_uncertain(tmp_path):
    store,snapshot,vlm=fixture(tmp_path)
    vlm.interpret=lambda *args:{'summary':'birds','criteria':[],'ambiguities':[],'unsupported':[],
        'requested_categories':[{'id':'birds','description':'Uccelli'}]}
    result=build_instruction_proposal(store,snapshot,vlm)
    assert result['shortlist']==[]
    assert all(a['match']=='uncertain' for a in result['assessments'].values())
    assert result['coverage'][0]['status']=='uncertain'


def test_prompt_explains_mixed_categories_and_default_portrait_people(tmp_path):
    from PIL import Image
    vlm=LocalVLM.__new__(LocalVLM)
    prompts=[]
    def structured(prompt,image,schema,max_tokens,**kwargs):
        prompts.append(prompt)
        return {}
    vlm._structured=structured
    vlm.interpret('uccelli e ritratti',[])
    assert "'uccelli e ritratti'" in prompts[0]
    assert "'Ritratti' senza specificazione indica persone" in prompts[0]
    preview=tmp_path/'synthetic.jpg'
    Image.new('RGB',(10,10),'white').save(preview)
    vlm.assess(preview,{'original_instructions':'uccelli e ritratti','requested_categories':[]})
    assert 'non richiedere tutte le altre nella stessa foto' in prompts[1]
    assert 'ritratti di persone, non ritratti di uccelli' in prompts[1]
    assert 'Le preferenze esplicite prevalgono sul tuo giudizio di bellezza' in prompts[1]
    assert 'composizione, espressività e significato del momento' in prompts[1]
    assert 'non assegnare automaticamente 0.5 a tutte' in prompts[1]
    assert 'non ridurre il punteggio contando difetti tecnici' in prompts[1].lower()
    assert 'registra i difetti in quality_issues' in prompts[1]
    assert 'Non sostituire un ritratto richiesto con un uccello più nitido' in prompts[1]


def test_placeholder_and_copied_subject_list_are_rejected_without_guesses(tmp_path):
    from lrc_selection.vlm import _validate_interpretation
    base={'summary':'synthetic','criteria':[],'ambiguities':[],'unsupported':[],
          'requested_categories':[{'id':'slug_stabile','description':'uccelli, ritratti, landscape'}]}
    with pytest.raises(ValueError,match='segnaposto'):
        Interpretation.model_validate(base)
    base['requested_categories'][0]['id']='soggetti'
    with pytest.raises(ValueError,match='sola categoria'):
        _validate_interpretation(base,'uccelli, ritratti, landscape')
    # General rule applies to other subject lists, not bird-specific substitution.
    base['requested_categories'][0]['description']='architettura, automobili, fiori'
    with pytest.raises(ValueError,match='sola categoria'):
        _validate_interpretation(base,'architettura, automobili, fiori')
    base['requested_categories']=[{'id':'architecture','description':'Architettura'},
        {'id':'cars','description':'Automobili'},{'id':'flowers','description':'Fiori'}]
    _validate_interpretation(base,'architettura, automobili, fiori')


def test_repair_has_actual_parse_error_and_schema_without_response_echo():
    vlm=LocalVLM.__new__(LocalVLM)
    prompts=[]
    answers=iter(['{"summary":"DO_NOT_ECHO",',json.dumps({'summary':'synthetic', 'criteria':[],
        'ambiguities':[],'unsupported':[],'requested_categories':[]})])
    def generate(prompt,image,max_tokens):
        prompts.append((prompt,max_tokens))
        return next(answers)
    vlm._generate=generate
    result=vlm.interpret('forme sintetiche',[])
    assert result['requested_categories']==[]
    assert len(prompts)==2 and all(tokens==1024 for _,tokens in prompts)
    assert 'JSON Schema' in prompts[0][0]
    assert 'slug_stabile' not in prompts[0][0] and 'id_categoria' not in prompts[0][0]
    assert 'invalid_json' in prompts[1][0] and 'campi principali' in prompts[1][0]
    assert 'DO_NOT_ECHO' not in prompts[1][0]


def test_category_key_mismatch_is_repaired_with_exact_expected_keys(tmp_path):
    from PIL import Image
    vlm=LocalVLM.__new__(LocalVLM)
    prompts=[]
    data={'match':'yes','reason':'synthetic bird','scene':'synthetic','quality_issues':[],
          'preference_score':.7,'category_matches':{'wrong':'yes'}}
    answers=iter([json.dumps(data),json.dumps(data | {'category_matches':{'birds':'yes'}})])
    def generate(prompt,image,max_tokens):
        prompts.append(prompt)
        assert max_tokens==1024
        return next(answers)
    vlm._generate=generate
    preview=tmp_path/'synthetic.jpg'
    Image.new('RGB',(10,10),'white').save(preview)
    result=vlm.assess(preview,{'original_instructions':'birds',
        'requested_categories':[{'id':'birds','description':'Birds'}]})
    assert result['category_matches']=={'birds':'yes'}
    assert len(prompts)==2
    assert 'category_matches deve contenere esattamente' in prompts[1]
    assert 'birds' in prompts[1]


def test_diagnostics_mark_invalid_and_missing_as_incomplete_then_retry(tmp_path):
    store,snapshot,vlm=fixture(tmp_path)
    snapshot['photos'][0]['preview_ready']=False
    vlm.fail=True
    failed=build_instruction_proposal(store,snapshot,vlm)
    assert failed['incomplete'] is True
    assert failed['diagnostics']=={'total':3,'attempted':2,'valid':0,'invalid':2,
        'missing_preview':1,'missing':1,'not_assessed':0,'yes':0,'no':0,'uncertain':3,
        'error_counts':{'schema':2}}
    assert any('analisi incompleta' in warning for warning in failed['warnings'])
    vlm.fail=False
    recovered=build_instruction_proposal(store,snapshot,vlm)
    assert recovered['diagnostics']['invalid']==0
    assert recovered['diagnostics']['valid']==2
    assert len(vlm.assess_calls)==4  # invalid responses were not stored as evidence
    snapshot['photos'][0]['preview_ready']=True
    completed=build_instruction_proposal(store,snapshot,vlm)
    assert completed['incomplete'] is False
    assert completed['diagnostics']['valid']==3


def test_local_reason_bound_does_not_change_shared_api_assessment_schema():
    from lrc_selection.vlm import Assessment, LocalAssessment
    data={'match':'yes','reason':'x'*200,'scene':'synthetic','quality_issues':[],
          'preference_score':.5,'category_matches':{}}
    assert Assessment.model_validate(data).reason==data['reason']
    with pytest.raises(ValueError):
        LocalAssessment.model_validate(data)
