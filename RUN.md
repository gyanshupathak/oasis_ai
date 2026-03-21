# Oasis — Run the full pipeline (UI → video)

## 1. One-time setup

**Windows (PowerShell)** — replace `path\to\Oasis` with your clone:

```powershell
cd path\to\Oasis

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

copy .env.example .env
# Edit .env — GEMINI_API_KEY and POLLINATIONS_API_KEY
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

## 2. Start the web app

```bash
cd web
npm install
npm run dev
```

Open **http://localhost:3000**

## 3. Create a reel

1. Paste your LinkedIn post in the text area.
2. Click **Create Reel**.
3. Wait for phases 1–6 to finish.
4. The video appears below when done.

## Example pipeline (UI / video-gen style)

| Phase | Task |
|-------|------|
| 1 | Scene planning (Gemini) |
| 2 | May be skipped depending on mode |
| 3 | Voiceover (Gemini TTS) |
| 4 | Video clips (Pollinations, etc.) |
| 5 | Assembly (concat + mux voiceover) |
| 6 | Caption/hashtags (if enabled) |

## Troubleshooting

- **Pipeline exited with code X** — Check terminal output. Often: missing API keys, Gemini quota (429), or Pollinations limits.
- **final.mp4 not found** — Pipeline failed before assembly; fix the error and re-run.
- **Video does not play** — Hard refresh or another browser.
- **Gemini 429** — Free tier limits; wait or upgrade.
- **FFmpeg not found** — Install FFmpeg on `PATH`, or rely on `imageio-ffmpeg` where the code uses it.

## CLI (no UI)

From repo root with venv active:

```bash
python main.py --text sample_post.txt --name "my-reel" --video-gen --no-caption
```

Output: `output/my-reel/final.mp4`

## Optional maintenance scripts

From repo root (venv active, same deps as the main pipeline):

```bash
python scripts/assemble_and_fix.py output/your-run-folder 60
python scripts/fix_final_h264.py output/your-run-folder
```

## Deployment and two-repo workflow

See [DEPLOY_AND_REPOS.md](DEPLOY_AND_REPOS.md).
