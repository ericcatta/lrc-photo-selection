#!/bin/zsh
set -euo pipefail
cd "${0:A:h:h}"
if [[ ! -x .venv/bin/lrc-selection || ! -f web/dist/index.html ]]; then
  echo 'Installazione incompleta. Segui README.md: ambiente Python e build web.'
  exit 1
fi
exec .venv/bin/lrc-selection
