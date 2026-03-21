# Oasis: Next.js (web/) + Python pipeline + FFmpeg in one image.
# Build: docker build -t oasis .
# Run:  docker run --env-file .env -p 3000:3000 oasis

FROM node:20-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    python3 \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN python3 -m venv .venv \
    && .venv/bin/pip install --no-cache-dir --upgrade pip \
    && .venv/bin/pip install --no-cache-dir -r requirements.txt

COPY web/package.json web/package-lock.json ./web/
RUN cd web && npm ci

COPY . .
RUN cd web && npm run build

ENV NODE_ENV=production
ENV PORT=3000
EXPOSE 3000

WORKDIR /app/web
CMD ["npm", "run", "start"]
