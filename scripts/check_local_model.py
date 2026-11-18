"""Offline adapter smoke check on generated shapes, never user photographs.

This checks compatibility/format/basic vision only, not photographic merit.
"""
import argparse
import json
import os
import tempfile
import time
from pathlib import Path

os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'

from PIL import Image, ImageDraw
from lrc_selection.vlm import LocalVLM


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    model = LocalVLM(args.model_dir)
    loaded = time.monotonic()
    results = []
    for text, expected in [('uccelli, ritratti, landscape', 3),
                           ('cerchi rossi e quadrati blu', 2)]:
        begin = time.monotonic()
        value = model.interpret(text, [])
        results.append({'kind': 'interpretation', 'instructions': text,
                        'seconds': time.monotonic() - begin, 'result': value,
                        'passed': len(value['requested_categories']) == expected})
        print(json.dumps({'check': text, 'passed': results[-1]['passed']}), flush=True)
    interpretation = results[-1]['result'] | {
        'original_instructions': 'cerchi rossi e quadrati blu',
        'original_criteria': [], 'original_subject_query': ''}
    with tempfile.TemporaryDirectory(prefix='lrc-synthetic-model-') as directory:
        for shape, expected in [('red_circle', 'yes'), ('blue_square', 'yes'), ('blank', 'no')]:
            preview = Image.new('RGB', (448, 448), 'white')
            draw = ImageDraw.Draw(preview)
            if shape == 'red_circle':
                draw.ellipse((100, 100, 348, 348), fill='red')
            elif shape == 'blue_square':
                draw.rectangle((100, 100, 348, 348), fill='blue')
            path = Path(directory) / (shape + '.png')
            preview.save(path)
            begin = time.monotonic()
            value = model.assess(path, interpretation)
            results.append({'kind': 'synthetic_image', 'fixture': shape,
                            'seconds': time.monotonic() - begin, 'result': value,
                            'passed': value['match'] == expected})
            print(json.dumps({'check': shape, 'passed': results[-1]['passed']}), flush=True)
    import mlx.core as mx
    report = {'synthetic_only': True, 'photo_quality_validated': False,
              'model_directory': args.model_dir.name,
              'runtime': model.identity['mlx_vlm'], 'load_seconds': loaded - started,
              'peak_memory_bytes': mx.get_peak_memory(),
              'seconds': time.monotonic() - started, 'checks': results,
              'passed': all(row['passed'] for row in results)}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != 'checks'}))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
