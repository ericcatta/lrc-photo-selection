"""Isolated synthetic scale check; never reads a catalog or user photograph.

Run: .venv/bin/python scripts/benchmark_scale.py
Results are timings, not claims about real-world model accuracy.
"""
import io
import json
import tempfile
import time
from pathlib import Path
from fastapi.testclient import TestClient
from PIL import Image
from lrc_selection.app import create_app


def measure(count):
    with tempfile.TemporaryDirectory(prefix='lrc-synthetic-scale-') as folder:
        app = create_app(Path(folder), token='synthetic-scale-only')
        with TestClient(app) as client:
            client.headers['Authorization'] = 'Bearer synthetic-scale-only'
            photos = [{'id': f'synthetic-{i}', 'uuid': f'synthetic-{i}', 'local_id': i,
                       'filename': 'SINTETICO.jpg', 'baseline_rating': 0,
                       'baseline_edit_time': 1.0} for i in range(count)]
            start = time.perf_counter()
            client.post('/api/imports', json={'schema_version': 1, 'id': 'synthetic',
                        'title': 'DATI SINTETICI — benchmark', 'catalog_id': 'synthetic',
                        'photos': photos}).raise_for_status()
            imported_seconds = time.perf_counter() - start
            image = io.BytesIO()
            Image.new('RGB', (24, 16), 'gray').save(image, 'JPEG')
            preview = '/api/services/synthetic/photos/synthetic-0/preview'
            client.put(preview, content=image.getvalue()).raise_for_status()
            service = client.post('/api/services/synthetic/complete').json()
            start = time.perf_counter()
            response = client.get('/api/services/synthetic')
            response.raise_for_status()
            detail_seconds = time.perf_counter() - start
            start = time.perf_counter()
            for _ in range(20):
                client.get(preview).raise_for_status()
            preview_seconds = (time.perf_counter() - start) / 20
            start = time.perf_counter()
            client.post('/api/services/synthetic/analyze', json={'revision': service['revision']}).raise_for_status()
            while True:
                service = client.get('/api/services/synthetic').json()
                if service['job']['status'] not in ('queued', 'running'):
                    break
                if time.perf_counter() - start > 60:
                    raise RuntimeError('Synthetic analysis timeout')
                time.sleep(.01)
            assert service['job']['status'] == 'completed', service['job']
            assert len(service['selected_ids']) == count
            return {'synthetic_photos': count, 'manifest_seconds': round(imported_seconds, 3),
                    'detail_seconds': round(detail_seconds, 3), 'detail_bytes': len(response.content),
                    'preview_request_seconds_mean_20': round(preview_seconds, 4),
                    'baseline_analysis_seconds': round(time.perf_counter() - start, 3),
                    'candidates_preserved': len(service['selected_ids'])}


if __name__ == '__main__':
    print(json.dumps([measure(1000), measure(5000)], indent=2))
