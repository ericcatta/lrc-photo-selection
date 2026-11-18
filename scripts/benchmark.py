"""Evaluate a saved proposal against human labels; never loads photo files.

Labels JSON: {"service_id":"...", "significant_groups":[["photo-id",...]],
"unique_images":["photo-id"], "must_separate_pairs":[["photo-id","photo-id"]]}.
Each benchmark uses an explicitly supplied data directory and labels file.
"""
import argparse
import json
from pathlib import Path
from lrc_selection.engine import effective_selected
from lrc_selection.store import Store


def evaluate(service, labels):
    ids = {p['id'] for p in service['photos']}
    if labels['service_id'] != service['id']:
        raise ValueError('Annotazioni di un altro servizio')
    groups = labels.get('significant_groups', [])
    unique = labels.get('unique_images', [])
    separate = labels.get('must_separate_pairs', [])
    mentioned = set(unique) | {p for g in groups for p in g} | {p for pair in separate for p in pair}
    if not mentioned <= ids or any(not g for g in groups) or any(len(p) != 2 for p in separate):
        raise ValueError('Annotazioni non valide')
    selected = set(effective_selected(service))
    automatic_groups = service.get('proposal', {}).get('groups', []) if service.get('proposal') else []
    return {'schema_version': 1, 'service_id': service['id'], 'revision': service['revision'],
            'engine': service['proposal']['engine'] if service.get('proposal') else 'manual',
            'significant_groups_lost': sum(not selected.intersection(g) for g in groups),
            'unique_images_excluded': len(set(unique) - selected),
            'person_compositions_merged': sum(any(set(pair) <= set(g['members']) for g in automatic_groups) for pair in separate),
            'locked_decisions_violated': sum((pid in selected) != (d['state'] in {'candidate', 'preferred', 'review'})
                                            for pid, d in service['decisions'].items() if d['locked']),
            'selected': len(selected), 'total': len(ids), 'target': service['settings']['target'],
            'preview_hashes': {p['id']: p.get('preview_sha256') for p in service['photos']},
            'note': 'Misure valide soltanto per le annotazioni e il campione forniti, non per tutte le situazioni reali.'}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', required=True, type=Path)
    parser.add_argument('--labels', required=True, type=Path)
    args = parser.parse_args()
    labels = json.loads(args.labels.read_text())
    print(json.dumps(evaluate(Store(args.data_dir).get(labels['service_id']), labels), indent=2, ensure_ascii=False))
