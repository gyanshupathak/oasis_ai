# Oasis — Run the Full Pipeline (UI → Video)

## 1. One-time setup

```powershell
cd d:\Oasis

# Python venv + deps (includes imageio-ffmpeg; no separate FFmpeg needed)
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# API keys
copy .env.example .env
# Edit .env — add GEMINI_API_KEY and POLLINATIONS_API_KEY
```

## 2. Start the web app

```powershell
cd d:\Oasis\web
npm install
npm run dev
```

Open **http://localhost:3000**

## 3. Create a reel

1. Paste your LinkedIn post in the text area.
2. Click **Create Reel**.
3. Watch phases 1–6 (scene plan → voiceover → video gen → assembly).
4. The video appears below when done.

## Pipeline (3 scenes ≈ 18 s)

| Phase | Task |
|-------|------|
| 1 | Scene planning (Gemini) |
| 2 | Skipped (video-gen mode) |
| 3 | Voiceover (Gemini TTS) |
| 4 | Video clips (Pollinations grok-video) |
| 5 | Assembly (concat + mux voiceover) |
| 6 | Skipped (--no-caption) |

## Troubleshooting

- **"Pipeline exited with code X"** — Check the Console output for the traceback. Often: missing API keys, Gemini quota (429), or Pollinations limits.
- **"final.mp4 not found"** — Pipeline failed before assembly. Re-run after fixing the error.
- **Video doesn’t play** — Hard refresh (Ctrl+F5) or try another browser.
- **Gemini 429** — Free tier limits (e.g. 10 TTS requests/day). Wait and retry, or upgrade.
- **FFmpeg not found** — `pip install imageio-ffmpeg` and re-run. The bundle includes FFmpeg.

## CLI (no UI)

```powershell
cd d:\Oasis
.venv\Scripts\activate
python main.py --text sample_post.txt --name "my-reel" --video-gen --no-caption
```

Output: `output/my-reel/final.mp4`
