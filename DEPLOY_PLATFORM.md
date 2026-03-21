# Deploy the full Oasis platform (UI + Python + FFmpeg)

Oasis is **one app** with two parts:

- **Next.js** (`web/`) — browser UI and API routes.
- **Python** (`main.py` + pipeline) — scene planning, images, TTS, video, FFmpeg assembly.

The API **starts Python as a subprocess** and needs **FFmpeg on the server**. That is why deployment is **Docker-first**. Plain **Vercel serverless** is not a good fit for the full pipeline (no bundled Python/FFmpeg in the same way, tight timeouts).

This guide assumes the repo is **[gyanshupathak/oasis_ai](https://github.com/gyanshupathak/oasis_ai)** with **`Dockerfile` at the repository root** (not inside `web/`).

---

## 1. What you are deploying

| Piece | Role |
|--------|------|
| **Docker image** | Node 20, Next production server, Python venv + `requirements.txt`, system **FFmpeg** |
| **Port** | **3000** (`PORT=3000`; Next reads this in production) |
| **Secrets** | `GEMINI_API_KEY`, `POLLINATIONS_API_KEY` (required for full run). Optional: `REPLICATE_API_TOKEN` (music). |
| **Disk** | Writes under `/app/output/<slug>/` during a run. On many hosts this is **ephemeral** (gone if the instance restarts). |
| **Time** | A full reel can take **several minutes**. The generate route is designed for long streams; the host must not kill the connection too early. |
| **RAM** | Video + Whisper + models: prefer **at least 2 GB** per instance if the host lets you choose. |

---

## 2. Before you touch any cloud provider

1. **Keys ready** (same names as `.env.example`):
   - `GEMINI_API_KEY`
   - `POLLINATIONS_API_KEY`
2. **Local Docker smoke test** (proves the image builds and starts):

   ```bash
   cd /path/to/Oasis   # repo root, where Dockerfile lives
   docker build -t oasis .
   docker run --rm -p 3000:3000 --env-file .env oasis
   ```

   Open `http://localhost:3000`, run a **short** test reel. If this fails, fix it locally before deploying.

3. **Repo pushed** to GitHub (`oasis_ai` or your fork) so hosts can build from Git.

---

## 3. Environment variables (set in the host UI, not in Git)

| Variable | Required | Purpose |
|----------|----------|---------|
| `GEMINI_API_KEY` | Yes (for full pipeline) | Scene plan, overlays, Gemini TTS |
| `POLLINATIONS_API_KEY` | Yes (for images/video as in your config) | Pollinations image/video APIs |
| `REPLICATE_API_TOKEN` | No | Optional music via Replicate |
| `NODE_ENV` | Usually auto | Should be `production` |
| `PORT` | Often auto | **3000** if the platform asks |

The app merges **process environment** with optional `.env` on disk; in Docker you typically **only** use the platform’s env var screen (no `.env` file in the image).

---

## 4. Option A — Fly.io (Docker, good for long requests)

**Idea:** Fly runs your container globally; you set secrets and scale VM memory.

1. Install CLI: [https://fly.io/docs/hands-on/install-flyctl/](https://fly.io/docs/hands-on/install-flyctl/)
2. Login: `fly auth login`
3. From your **local clone** of the repo (root contains `Dockerfile`):

   ```bash
   fly launch
   ```

   - Choose app name and region.
   - **Use the existing Dockerfile** when prompted (do not replace with a minimal template if asked).
   - You can decline Postgres/Redis unless you add them later.

4. **Do not** put API keys in `fly.toml`. Set secrets:

   ```bash
   fly secrets set GEMINI_API_KEY="your_key" POLLINATIONS_API_KEY="your_key"
   ```

5. **Memory:** In `fly.toml`, under `[[vm]]`, increase memory if builds OOM or pipeline crashes (e.g. **2048** MB or higher). Redeploy after edits: `fly deploy`.

6. Deploy:

   ```bash
   fly deploy
   ```

7. Open the URL Fly prints (e.g. `https://your-app.fly.dev`).

**Notes:** Check Fly’s current free allowance and pricing. For reels, avoid **auto-suspend** killing a run mid-flight if your plan supports keeping one machine up for requests.

---

## 5. Option B — Railway

**Idea:** Connect GitHub repo; Railway builds the Dockerfile and runs the container.

1. Go to [railway.app](https://railway.app), sign in with GitHub.
2. **New project** → **Deploy from GitHub repo** → select `oasis_ai`.
3. Railway may auto-detect Node; force **Dockerfile** deploy:
   - Set **root directory** to the repo root (where `Dockerfile` is).
   - Build strategy: **Dockerfile** (not Nixpacks-only).
4. **Variables** tab: add `GEMINI_API_KEY`, `POLLINATIONS_API_KEY`, and any optional keys.
5. **Generate domain** (Settings → Networking) to get a public HTTPS URL.
6. Deploy and watch build logs; fix Dockerfile or env if the build fails.

**Notes:** Confirm **timeout / request limits** on your plan for long SSE responses. Upgrade or adjust if the client disconnects during long jobs.

---

## 6. Option C — Render

**Idea:** Web service from a **Docker** repo.

1. [dashboard.render.com](https://dashboard.render.com) → **New** → **Web Service**.
2. Connect **oasis_ai**, branch `main`.
3. Environment: **Docker**.
4. **Dockerfile path:** `Dockerfile` (root).
5. **Instance type:** Pick one with enough **RAM** (see section 1).
6. **Environment** → add `GEMINI_API_KEY`, `POLLINATIONS_API_KEY`.
7. Deploy. URL will be like `https://your-service.onrender.com`.

**Notes:** Free web services **spin down** when idle; first request after idle can be **very slow** (cold start + possible model downloads). Paid instances stay up.

---

## 7. Option D — Any VPS (DigitalOcean, Hetzner, Lightsail, etc.)

**Idea:** Ubuntu server + Docker Engine; you manage TLS (e.g. Caddy or nginx + Let’s Encrypt).

1. Install Docker on the server ([Docker Engine docs](https://docs.docker.com/engine/install/)).
2. Clone the repo or `docker pull` a registry image you pushed from CI.
3. Run:

   ```bash
   docker build -t oasis .
   docker run -d --restart unless-stopped -p 3000:3000 \
     -e GEMINI_API_KEY="..." \
     -e POLLINATIONS_API_KEY="..." \
     --name oasis \
     oasis
   ```

4. Put a reverse proxy in front for HTTPS and (optionally) rate limiting.

---

## 8. After deploy — how to verify

1. Open the site root — you should see the **Oasis** UI.
2. Run a **short** post (small scene count if your UI allows) and watch logs on the host.
3. If video fails: check logs for missing keys, FFmpeg errors, or OOM (out of memory).

---

## 9. Common problems

| Symptom | Likely cause |
|---------|----------------|
| Build fails on `npm run build` | Node/Next issue; run `cd web && npm run build` locally on same commit. |
| Build fails on `pip install` | `requirements.txt` pins or system deps; check build log. |
| 502 / instant disconnect on “Create reel” | Timeout too short, or process crashed (check RAM). |
| “API key not set” | Env vars not set for **runtime** (not only build). |
| Works once, empty after restart | Ephemeral disk; expected unless you add persistent volume / object storage. |
| First run very slow | **faster-whisper** may download models on first use; cold start. |

---

## 10. What we are *not* doing in this guide

- **Vercel-only** deploy of `web/` without a Docker worker — the **generate** route will not have a working Python+FFmpeg sibling unless you re-architect (queue + worker).
- **Committing `.env`** to Git — never.

---

## 11. Quick reference commands

```bash
# Local build + run
docker build -t oasis .
docker run --rm -p 3000:3000 --env-file .env oasis

# Fly.io
fly secrets set GEMINI_API_KEY="..." POLLINATIONS_API_KEY="..."
fly deploy
```

For repo layout and two-remote workflow, see **[DEPLOY_AND_REPOS.md](DEPLOY_AND_REPOS.md)**.
