# Oasis MVP 0.1

Convert LinkedIn/Twitter posts into Instagram Reels. A deterministic pipeline: Text → Scene Plan → Images → Voiceover → Video → Caption.

## Prerequisites

- Python 3.10+
- FFmpeg (install: `choco install ffmpeg` on Windows)

## API Keys

| Key | Used for | Get it |
|-----|----------|--------|
| `GEMINI_API_KEY` | Scene plan, voiceover | [Google AI Studio](https://aistudio.google.com/apikey) (free) |
| `POLLINATIONS_API_KEY` | Images + video generation | [enter.pollinations.ai](https://enter.pollinations.ai) (3 pollen/day free) |

## Setup

```bash
cd d:\Oasis
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# Edit .env: add GEMINI_API_KEY and POLLINATIONS_API_KEY
```

## Web UI (Next.js)

**Run from Oasis root** so the API can find `main.py` and `.env`:

```bash
cd d:\Oasis
cd web
npm install
npm run dev
```

Open http://localhost:3000. Paste your LinkedIn post, pick a preset (30 sec / 60 sec / 24 sec), hit Create Reel, and watch the pipeline phases. The video appears below when done, with caption and hashtags.

## Usage

**Full pipeline** (post text → final.mp4 + caption + hashtags):

```bash
python main.py --text "Your LinkedIn post here..."
# Or from file:
python main.py --text sample_post.txt
```

**Options:**
- `--name "2026 recap post"` — Folder name for this run (slug → `output/2026-recap-post/`)
- `--video-gen` — Use Pollinations video gen (grok-video)
- `--no-voiceover` — Skip Gemini TTS voiceover
- `--no-caption` — Skip caption and hashtags
- `--length 45` — Target reel length in seconds
- `--output output` — Base output directory (run folders go inside)
- `--phase N` — Run only phases 1..N
- `--plan path` — Use existing scene_plan.json (output dir = plan's parent)

## Output

Each run writes to a **separate folder** under `output/`:

```
output/
  2026-recap-post/     ← --name "2026 recap post"
    scene_plan.json
    scene_1.mp4, scene_2.mp4, ...
    voiceover.wav
    final.mp4
    caption.txt
    hashtags.txt
```

Without `--name`, the folder is auto-derived from the first line of the post.

## Pipeline Phases

**With `--video-gen`** (Pollinations video instead of FFmpeg):

| Phase | What it does |
|-------|--------------|
| 1 | Scene plan (Gemini) |
| 2 | Skipped (video is text-to-video) |
| 3 | Voiceover (Gemini TTS) |
| 4 | Video gen (Pollinations grok-video) — one clip per scene |
| 5 | Assemble (FFmpeg concat + mux voiceover) |
| 6 | Caption + hashtags (optional, use `--no-caption` to skip) |

**Without `--video-gen`** (default, FFmpeg from images):

| Phase | What it does |
|-------|--------------|
| 1 | Scene plan |
| 2 | Images (Pollinations flux) |
| 3 | Voiceover |
| 4 | Assemble (FFmpeg zoompan + text + concat + mux) |
| 6 | Caption + hashtags |

## Font (Video Text)

FFmpeg `drawtext` uses system fonts. On Windows, Arial is usually available. If text doesn't render, install a font and set `FONT` in `video_assembler.py` to the font name or path.
