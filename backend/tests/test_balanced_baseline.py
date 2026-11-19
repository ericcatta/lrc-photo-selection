"""Only synthetic IDs and preview hashes; no files or catalog access."""
from collections import Counter
from copy import deepcopy
from lrc_selection.engine import analyze


def service(group_count=10, variants=4, target=20):
    return {'photos': [{'id': f'{group}-{variant}', 'preview_sha256': f'synthetic-{group}'}
                       for group in range(group_count) for variant in range(variants)],
            'settings': {'target': target}, 'decisions': {}}


def test_exact_duplicates_fill_balanced_rounds_not_import_order():
    source = service()
    before = deepcopy(source)
    result = analyze(source)
    assert len(result['selected']) == 20
    assert Counter(pid.split('-')[0] for pid in result['selected']) == {str(g): 2 for g in range(10)}
    assert source == before


def test_distinct_baseline_groups_can_exceed_target():
    result = analyze(service(group_count=23, variants=2))
    assert len(result['selected']) == 23
    assert all(pid.endswith('-0') for pid in result['selected'])


def test_manual_duplicate_choices_count_toward_rounds_and_exclusions_remain():
    source = service(group_count=3, variants=4, target=6)
    source['decisions'] = {'0-0': {'state': 'preferred'}, '0-1': {'state': 'candidate'},
                           '0-2': {'state': 'review'}, '1-0': {'state': 'excluded'}}
    result = analyze(source)
    assert {'0-0', '0-1', '0-2'} <= set(result['selected'])
    assert '1-0' not in result['selected']
    assert '0-3' not in result['selected']
    assert len(result['selected']) == 6
