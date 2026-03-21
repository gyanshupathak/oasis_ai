# Oasis MVP 0.1

Convert LinkedIn/Twitter posts into Instagram Reels. Pipeline: **Text → Scene plan → Images → Voiceover → Video → Assembly → Caption.**

Built with [pollinations.ai](https://pollinations.ai) for image and video generation.

[![Built with pollinations.ai](https://pollinations.ai/badge)](https://pollinations.ai)

## Prerequisites

- **Python 3.10+**
- **FFmpeg** on `PATH` (e.g. Windows: `choco install ffmpeg`; macOS: `brew install ffmpeg`; Linux: `apt install ffmpeg`)
- **Node.js 18+** (only if you use the Next.js UI under `web/`)

## API keys

| Key | Used for | Get it |
|-----|----------|--------|
| `GEMINI_API_KEY` | Scene plan, overlays, voiceover (Gemini TTS) | [Google AI Studio](https://aistudio.google.com/apikey) |
| `POLLINATIONS_API_KEY` | Images + Pollinations video | [enter.pollinations.ai](https://enter.pollinations.ai) |
| `REPLICATE_API_TOKEN` | Optional: AI music via Replicate | [replicate.com](https://replicate.com/account) (see `.env.example`) |

Copy `.env.example` to `.env` and fill in values. **Do not commit `.env`.**

## Setup (clone anywhere)

**Windows (PowerShell):**

```powershell
cd path\to\Oasis
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# Edit .env: GEMINI_API_KEY, POLLINATIONS_API_KEY
```

**macOS / Linux:**

```bash
cd path/to/Oasis
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env
```

## Web UI (Next.js)

Run **from the repository root** so the API can find `main.py` and `.env`:

```bash
cd path/to/Oasis/web
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Paste post text, choose a preset, run the pipeline. More detail: [web/README.md](web/README.md).

## CLI usage

Full pipeline (post → `final.mp4` + caption + hashtags):

```bash
python main.py --text "Your LinkedIn post here..."
python main.py --text sample_post.txt
```

**Common flags:**

| Flag | Meaning |
|------|---------|
| `--name "my reel"` | Output folder under `output/` (slugified) |
| `--video-gen` | Use Pollinations video generation path |
| `--no-voiceover` | Skip TTS |
| `--no-caption` | Skip caption/hashtags export |
| `--length 45` | Target reel length (seconds) |
| `--output output` | Base output directory |
| `--phase N` | Run phases 1..N only |
| `--plan path` | Use existing `scene_plan.json` |

## Output layout

Each run writes under `output/<slug>/`:

- `scene_plan.json`, scene images/videos, `voiceover.*`, `final.mp4`, `caption.txt`, `hashtags.txt`

Without `--name`, the slug is derived from the first line of the post.

## Pipeline phases (summary)

**With `--video-gen`:** scene plan → (images may be skipped depending on mode) → voiceover → Pollinations video clips → assemble → optional caption pack.

**Without `--video-gen` (default):** scene plan → images → voiceover → per-scene video (I2V / FFmpeg fallback) → assemble → packaging.

Details: [PIPELINE_AND_TECH.md](PIPELINE_AND_TECH.md).

## Font (burned subtitles)

FFmpeg `drawtext` uses system fonts. On Windows, Arial is usually available. If text does not render, set the font in `video_assembler.py` to a valid name or file path.

## Docker (full working UI + Python + FFmpeg)

From repo root (requires [Docker](https://docs.docker.com/get-docker/)):

```bash
docker build -t oasis .
docker run --env-file .env -p 3000:3000 oasis
```

Open [http://localhost:3000](http://localhost:3000). Use the same keys as in `.env.example`. For cloud hosts (Fly.io, Railway, Render), point the service at this `Dockerfile` and set `GEMINI_API_KEY` and `POLLINATIONS_API_KEY` in the dashboard.

**Full step-by-step cloud deploy:** **[DEPLOY_PLATFORM.md](DEPLOY_PLATFORM.md)**.  
**$0 / no-budget path (local + Cloudflare Tunnel or Fly free tier):** **[FREE_DEPLOY_STEP_BY_STEP.md](FREE_DEPLOY_STEP_BY_STEP.md)**.

## Private repo, public repo, deployment

Step-by-step: **[DEPLOY_AND_REPOS.md](DEPLOY_AND_REPOS.md)** (backup to private GitHub, keep `oasis_ai` clean, realistic free hosting options).

## More docs

- [RUN.md](RUN.md) — full pipeline from UI, troubleshooting  
- [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) — high-level overview for workflow design  
