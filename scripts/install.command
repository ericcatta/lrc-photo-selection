#!/bin/zsh
# Installs this checkout only. No model download, API call or Lightroom access.
set -euo pipefail
cd "${0:A:h:h}"

if ! command -v python3 >/dev/null 2>&1; then
  echo 'Python 3 non trovato. Installa Python 3.11 o successivo, poi riprova.' >&2
  exit 1
fi
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else "Serve Python 3.11 o successivo.")'
if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  echo 'Node.js e npm non trovati. Installa una versione compatibile indicata nel README, poi riprova.' >&2
  exit 1
fi
node -e 'const [major, minor] = process.versions.node.split(".").map(Number); if (!(major > 22 || (major === 22 && minor >= 12) || (major === 20 && minor >= 19))) { console.error("Serve Node.js 20.19+ della serie 20, oppure 22.12 o successivo."); process.exit(1); }'
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
if [[ ! -x .venv/bin/python ]]; then
  echo 'La cartella .venv esiste ma non contiene un ambiente valido. Rinominala manualmente e riprova.' >&2
  exit 1
fi
.venv/bin/python -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else "L’ambiente .venv richiede Python 3.11 o successivo: rinominalo e riprova.")'

echo 'Installazione delle dipendenze Python nell’ambiente .venv del progetto…'
.venv/bin/python -m pip install -e .
echo 'Installazione e compilazione dell’interfaccia…'
npm --prefix web ci
npm --prefix web run build

echo ''
echo 'Installazione completata.'
echo 'Avvia scripts/start.command e lascia aperta la finestra del backend.'
echo 'Poi aggiungi plugin/lrc-photo-selection.lrplugin da Gestione plug-in di Lightroom.'
echo 'Nessun modello scaricato, nessuna analisi avviata e nessun catalogo aperto.'
