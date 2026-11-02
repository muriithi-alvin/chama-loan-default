#!/usr/bin/env bash
# Starts Kibaba's release (D-032): on the first start, the demo chama is
# loaded into the empty database and scored; then the API, the worker and the
# pages run side by side. If any of the three stops, the container stops and
# Hugging Face starts it again.
set -euo pipefail
cd /app

python -m chama.pipeline first-start

python -m uvicorn chama.web.app:app --host 127.0.0.1 --port 8000 &
python -m chama.web.worker &
(cd frontend/.next/standalone && PORT=7860 HOSTNAME=0.0.0.0 exec node server.js) &

wait -n
exit $?
