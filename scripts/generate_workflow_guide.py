#!/usr/bin/env python3
"""Generate offline guide copies for Lightroom and web; --check detects drift."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs/workflow-guide.json'


def lua(value):
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        return '{' + ', '.join(lua(item) for item in value) + '}'
    if isinstance(value, dict):
        return '{' + ', '.join('[' + lua(key) + '] = ' + lua(item) for key, item in value.items()) + '}'
    raise ValueError('Unsupported guide value')


def outputs():
    guide = json.loads(SOURCE.read_text())
    assert guide['schema_version'] == 1 and len(guide['steps']) == 7
    assert len({step['id'] for step in guide['steps']}) == 7
    return {
        ROOT / 'web/src/guide-data.json': json.dumps(guide, ensure_ascii=False, indent=2) + '\n',
        ROOT / 'plugin/lrc-photo-selection.lrplugin/GuideData.lua': '-- Generated from docs/workflow-guide.json; do not edit.\nreturn ' + lua(guide) + '\n',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    for path, content in outputs().items():
        if args.check:
            if not path.exists() or path.read_text() != content:
                parser.exit(1, f'Guide copy out of date: {path.relative_to(ROOT)}\n')
        else:
            path.write_text(content)


if __name__ == '__main__':
    main()
