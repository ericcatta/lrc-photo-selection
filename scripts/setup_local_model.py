"""Explicit download step; application inference never downloads models."""
import argparse
import json
import os
from pathlib import Path

REPO = 'mlx-community/Qwen3-VL-4B-Instruct-4bit'
REVISION = '2fd8dacbdb8f1e54b8c005f081ec5bf79c56376b'


def main():
    parser = argparse.ArgumentParser(description='Scarica il modello visivo locale Qwen3-VL 4B; nessuna fotografia viene inviata')
    parser.add_argument('--data-dir', type=Path, default=Path.home() / 'Library/Application Support/LrC Photo Selection')
    args = parser.parse_args()
    os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
    from huggingface_hub import snapshot_download
    target = args.data_dir / 'models' / 'Qwen3-VL-4B-Instruct-4bit'
    snapshot_download(REPO, revision=REVISION, local_dir=target,
                      allow_patterns=['*.json', '*.safetensors', '*.txt', '*.jinja', '*.model', 'README.md', 'LICENSE*'])
    (target / 'provenance.json').write_text(json.dumps({'repo': REPO, 'revision': REVISION, 'license': 'Apache-2.0'}))
    print('Modello locale disponibile. Nessuna analisi avviata.')


if __name__ == '__main__':
    main()
