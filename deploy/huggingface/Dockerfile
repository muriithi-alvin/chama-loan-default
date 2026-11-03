# Kibaba's release on a Hugging Face Docker Space (decision D-032).
#
# The Space holds only this file and README.md. When Hugging Face builds the
# image it fetches, with build secrets:
#   - the code, from the private GitHub repository (secret GITHUB_TOKEN:
#     a fine-grained token that can only read this repository);
#   - the demo chama's typed pages, its fictional names and the champion
#     model, from a private Hugging Face dataset (secret HF_TOKEN: read-only).
# Neither the code nor any data is visible in the public Space.
#
# Space variables (passed to the build): GITHUB_REPO, GIT_REF, BUNDLE_REPO.
# Space secrets (also read at run time): see docs/deployment.md.

FROM node:24-bookworm-slim AS node

FROM python:3.11-slim-bookworm
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DO_NOT_TRACK=1 NEXT_TELEMETRY_DISABLED=1 MLFLOW_DISABLE_AGENT_HINT=1 \
    CHAMA_ONLY=chama_demo MODEL_BUNDLE=/app/bundle/model
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates postgresql \
    && rm -rf /var/lib/apt/lists/*
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && useradd -m -u 1000 user

ARG GITHUB_REPO=muriithi-alvin/chama-loan-default
ARG GIT_REF=main
ARG BUNDLE_REPO
RUN --mount=type=secret,id=GITHUB_TOKEN,mode=0444,required=true \
    git clone --depth 1 --branch "$GIT_REF" \
      "https://x-access-token:$(cat /run/secrets/GITHUB_TOKEN)@github.com/${GITHUB_REPO}.git" /app \
    && git -C /app remote remove origin

WORKDIR /app
# constraints.txt holds the versions the model was saved and tested with (pip
# freeze of the project environment): a model saved under one scikit-learn may
# not load under another.
RUN pip install -c deploy/huggingface/constraints.txt -e ".[ml,extraction,web]" huggingface_hub

RUN --mount=type=secret,id=HF_TOKEN,mode=0444,required=true \
    test -n "$BUNDLE_REPO" && python -c "import os; from huggingface_hub import snapshot_download; \
snapshot_download(repo_id=os.environ['BUNDLE_REPO'], repo_type='dataset', local_dir='/app/bundle', \
token=open('/run/secrets/HF_TOKEN').read().strip())" \
    && cp -r /app/bundle/data/. /app/data/

WORKDIR /app/frontend
RUN npm ci && NEXT_OUTPUT=standalone npm run build \
    && cp -r .next/static .next/standalone/.next/static \
    && cp -r public .next/standalone/public \
    && rm -rf node_modules .next/cache

WORKDIR /app
RUN mkdir -p data/logs data/interim/uploads && chown -R user:user /app
USER user
EXPOSE 7860
CMD ["bash", "deploy/huggingface/start.sh"]
