FROM node:24-bookworm-slim AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ENV NEXT_OUTPUT=standalone \
    NEXT_TELEMETRY_DISABLED=1 \
    API_URL=http://api:8000

RUN npm run build \
    && mkdir -p .next/standalone/.next \
    && cp -r .next/static .next/standalone/.next/static \
    && if [ -d public ]; then cp -r public .next/standalone/public; fi

FROM node:24-bookworm-slim AS runner

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000

WORKDIR /app

COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static

RUN if [ -d /app/public ]; then chown -R node:node /app/public; fi

USER node

EXPOSE 3000

CMD ["node", "server.js"]
