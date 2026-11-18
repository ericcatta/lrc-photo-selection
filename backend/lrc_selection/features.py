"""Explicit, offline feature extraction on already imported previews only.

Does not download weights, access original file paths, identify people, or reduce
candidates. Uncalibrated similarity is presented as review evidence, not truth.
"""
import argparse
import hashlib
import json
import platform
import subprocess
from pathlib import Path

from .store import Store

class SiglipEncoder:
    def __init__(self, model_dir: Path):
        if not model_dir.is_dir():
            raise ValueError('Indicare una directory locale di pesi già scaricati e verificati')
        # Imports are lazy so the complete manual/local baseline needs no ML stack.
        import torch
        from transformers import AutoModel, AutoProcessor
        self.torch = torch
        self.device = 'mps' if torch.backends.mps.is_available() else 'cpu'
        self.processor = AutoProcessor.from_pretrained(str(model_dir), local_files_only=True, trust_remote_code=False)
        self.model = AutoModel.from_pretrained(str(model_dir), local_files_only=True, trust_remote_code=False).to(self.device).eval()
        config = self.model.config
        if getattr(config, 'model_type', '') != 'siglip2':
            raise ValueError('Questo adattatore accetta soltanto checkpoint SigLIP 2')
        hashes = {}
        for path in sorted(model_dir.rglob('*')):
            if path.is_file() and path.suffix in ('.json', '.safetensors'):
                digest = hashlib.sha256()
                with path.open('rb') as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                        digest.update(chunk)
                hashes[str(path.relative_to(model_dir))] = digest.hexdigest()
        self.identity = {'adapter': 'siglip2-v1', 'files': hashes, 'device': self.device,
                         'torch': torch.__version__}

    def encode(self, path):
        from PIL import Image
        with Image.open(path) as source:
            image = source.convert('RGB')
        inputs = self.processor(images=image, return_tensors='pt').to(self.device)
        with self.torch.inference_mode():
            vector = self.model.get_image_features(**inputs)
            vector = vector / vector.norm(dim=-1, keepdim=True).clamp(min=1e-12)
        return vector[0].float().cpu().tolist()

def face_rectangles(tool, path):
    completed = subprocess.run([str(tool), str(path)], check=True, capture_output=True, timeout=120)
    result = json.loads(completed.stdout)[0]
    return {'engine': 'Apple Vision VNDetectFaceRectanglesRequest', 'os': platform.mac_ver(),
            'observations': result['faces'], 'error': result.get('error'),
            'warning': 'Nessun volto rilevato non significa nessuna persona. Identità non confrontata.'}

def extract(store, sid, encoder=None, vision_tool=None):
    service = store.get(sid)
    if service['status'] != 'ready':
        raise ValueError('Servizio non pronto')
    revision = service['revision']
    records = {}
    for photo in service['photos']:
        if not photo['preview_ready']:
            records[photo['id']] = {'error': 'Anteprima mancante'}
            continue
        path = store.preview_path(sid, photo['id'])
        record = {'preview_sha256': photo['preview_sha256']}
        if encoder:
            record['embedding'] = encoder.encode(path)
        if vision_tool:
            record['faces'] = face_rectangles(vision_tool, path)
        records[photo['id']] = record
    evidence = {'schema_version': 1, 'model': encoder.identity if encoder else None, 'records': records,
                'warning': 'Evidenze non calibrate: nessuna foto esclusa automaticamente sulla base di questi segnali.'}
    with store.transaction() as db:
        latest = store.get(sid, db)
        store.check_revision(latest, revision)
        if latest['status'] != 'ready':
            raise ValueError('Servizio occupato: estrazione non applicata')
        latest['interpretations'] = evidence
        latest['revision'] += 1
        store.put(db, latest)
    return evidence

def main():
    parser = argparse.ArgumentParser(description='Estrae segnali locali soltanto da anteprime già importate; nessun download')
    parser.add_argument('--data-dir', required=True, type=Path)
    parser.add_argument('--service-id', required=True)
    parser.add_argument('--siglip-dir', type=Path)
    parser.add_argument('--vision-tool', type=Path)
    args = parser.parse_args()
    if not args.siglip_dir and not args.vision_tool:
        parser.error('Specificare almeno un componente locale')
    encoder = SiglipEncoder(args.siglip_dir) if args.siglip_dir else None
    result = extract(Store(args.data_dir), args.service_id, encoder, args.vision_tool)
    print(f"Evidenze salvate per {len(result['records'])} foto; selezione non modificata.")

if __name__ == '__main__':
    main()
