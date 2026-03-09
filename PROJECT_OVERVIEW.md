# Oasis — Project Overview for Workflow Optimization

> **Purpose:** Paste this document into ChatGPT (or similar) to get suggestions for better workflows to produce professional-looking Instagram Reels from LinkedIn/Twitter text.

---

## 1. What Oasis Does

**Oasis** converts a LinkedIn or Twitter post (plain text) into a short Instagram Reel (vertical 9:16 video) with:

- AI-generated **scene plan** (hook, build, payoff)
- AI-generated **images** per scene (keyframes for I2V)
- AI-generated **video** from images (or text-to-video)
- AI **voiceover** (TTS) with word-by-word subtitles
- **Final assembly**: concatenate clips, mux audio, burn subtitles

**Target output:** Professional, scroll-stopping Reels suitable for creators and brands.

---

## 2. High-Level Pipeline (6 Phases)

```
Input: Post text (or path to .txt)
    ↓
Phase 1: Scene Planning (LLM) — Post → JSON scene plan
Phase 1.5: Overlay Planning (LLM) — Per-scene text/logo placement
Phase 2: Image Generation — 1 or 4 keyframes per scene (for I2V)
Phase 3: Voiceover — TTS from concatenated scene voiceover text
Phase 4: Video Generation — Image-to-video (I2V) or text-to-video (T2V)
Phase 5: Assembly — Concat clips, mux voiceover, burn subtitles
Phase 6: Packaging — caption.txt, hashtags.txt
    ↓
Output: final.mp4, caption.txt, hashtags.txt
```

---

## 3. File Structure

| File | Role |
|------|------|
| `main.py` | CLI entry, orchestrates phases 1–6 |
| `config.py` | Constants (MIN_SCENES, MAX_ON_SCREEN_WORDS, etc.) |
| `scene_planner.py` | Phase 1: Post → scene_plan.json (Gemini) |
| `overlay_planner.py` | Phase 1.5: Overlay config per scene (Gemini) |
| `image_generator.py` | Phase 2: Pollinations.ai images (klein/flux) |
| `voiceover.py` | Phase 3: TTS (Gemini → edge-tts → gTTS) |
| `video_generator.py` | Phase 4: Wan/Replicate/Grok I2V/T2V, FFmpeg fallback |
| `video_assembler.py` | Phase 5: FFmpeg concat, mux, ASS subtitles |
| `output_packager.py` | Phase 6: caption.txt, hashtags.txt |
| `models.py` | Pydantic/typed scene structure (optional) |

---

## 4. Model Fallback Chains (Best → Worst)

Each modality has a fallback chain: if one model fails (quota, rate limit, error), the next is tried.

### Text (LLM)

| Phase | Primary | Fallback 1 | Fallback 2 |
|-------|---------|------------|------------|
| Scene planning | `gemini-2.5-flash` | `gemini-2.5-flash-lite` | — |
| Overlay planning | `gemini-2.5-flash` | `gemini-2.5-flash-lite` | Sensible defaults (no LLM) |

### Images

| Primary | Fallback |
|---------|----------|
| Pollinations `klein` (FLUX.2 Klein) | Pollinations `flux` |

*Note: Both require POLLINATIONS_API_KEY. No third fallback (e.g. Replicate images) currently.*

### Audio (TTS)

| Primary | Fallback 1 | Fallback 2 |
|---------|------------|------------|
| Gemini `gemini-2.5-flash-preview-tts` | edge-tts (Microsoft, free) | gTTS (Google, free) |

Gemini TTS has ~10 requests/day on free tier; edge-tts and gTTS have no quota.

### Video

| Primary | Fallback 1 | Fallback 2 | Fallback 3 |
|---------|------------|------------|------------|
| Pollinations Wan (I2V) | Replicate minimax/video-01 (I2V) | Pollinations Grok (T2V) | FFmpeg zoompan on image |

I2V = image-to-video (needs start frame). T2V = text-to-video (no image). FFmpeg = animate single image with zoom when all AI video APIs fail.

---

## 5. Detailed Phase Descriptions

### Phase 1: Scene Planning (`scene_planner.py`)

- **Input:** Raw post text, target duration (e.g. 30s), number of scenes (e.g. 5)
- **Output:** `scene_plan.json` with:
  - `scenes`: array of `{ scene_id, purpose, visual_description, on_screen_text, voiceover, duration }`
  - `total_duration`, `caption`, `hashtags`

**Prompt highlights:**
- Hook rewriting: Scene 1 must be punchy, provocative, stop-the-scroll
- `visual_description`: 1–2 sentences, detailed for AI video model (lighting, angle, mood, style)
- Emotional arc: Hook → Build → Payoff
- JSON output only, no prose

### Phase 1.5: Overlay Planning (`overlay_planner.py`)

- **Input:** scene_plan with scenes
- **Output:** Each scene enriched with `overlay`: `{ text: { show, content, position, start_time, end_time, effect }, logo: { enabled, position } }`
- **Purpose:** Decide where and when to show on-screen text, whether to show logo

### Phase 2: Image Generation (`image_generator.py`)

- **Input:** `visual_description` per scene
- **Output:** `scene_N.png` (and optionally `scene_N_f1..f4.png` for 4 keyframes)
- **Prompt prefix/suffix:** `"Vertical cinematic photograph. " + desc + " Soft lighting, shallow depth of field. Aspect ratio 9:16. High quality, professional."`
- **Resolution:** 576×1024 (9:16)

### Phase 3: Voiceover (`voiceover.py`)

- **Input:** Concatenated `voiceover` text from all scenes
- **Output:** `voiceover.wav` (Gemini) or `voiceover.mp3` (edge-tts/gTTS)
- **Subtitle timing:** faster-whisper transcribes audio → word-by-word events; fallback: proportional timing from plan

### Phase 4: Video Generation (`video_generator.py`)

- **Input:** Per-scene `visual_description` + `scene_N.png` (first frame)
- **Output:** `scene_N.mp4` per scene (~2–15s each)
- **Image upload:** Required for I2V (Pollinations, Replicate). Uses tmpfiles.org, 0x0.st, transfer.sh, etc.
- **FFmpeg fallback:** Single image + zoompan filter → static-looking but functional clip

### Phase 5: Assembly (`video_assembler.py`)

- Concat all `scene_N.mp4` in order
- Mux voiceover: video duration adjusted to match voiceover (source of truth)
- Burn ASS subtitles: word-by-word, font 76px, outline 5, bottom margin 80
- Trim to `max_duration_sec` if specified

### Phase 6: Packaging (`output_packager.py`)

- Write `caption.txt`, `hashtags.txt` from scene plan

---

## 6. Current Design Decisions

- **Vertical 9:16** only (Instagram Reel format)
- **Word-by-word subtitles** (one word at a time, not phrase chunks)
- **Voiceover as source of truth** for final duration (video stretched/compressed to match)
- **No preset modes** — always cinematic (AI images + AI video)
- **Free-tier focus** — Gemini, Pollinations, edge-tts, gTTS where possible

---

## 7. Known Limitations & Pain Points

1. **Gemini quotas:** Scene planner, overlay planner, and TTS all share Gemini free tier; 429 errors common
2. **Pollinations video:** Wan 2.6 often returns 500; Replicate minimax sometimes fails; Grok T2V unreliable
3. **Image quality:** Pollinations klein/flux — decent but not always “professional”
4. **No human-in-the-loop:** No review step before assembly
5. **Single voice:** TTS voice is fixed (Puck for Gemini, Christopher for edge-tts)
6. **No B-roll or stock footage:** All visuals from AI image/video
7. **Prompt engineering:** `visual_description` quality varies; weak prompts → weak videos
8. **Subtitles:** ASS format, Arial; no brand styling or animation
9. **No music bed:** Voiceover only, no background music
10. **No transition effects:** Hard cuts between scenes

---

## 8. Tech Stack

- **Python 3.12+**
- **APIs:** Google Gemini, Pollinations.ai, Replicate (optional)
- **Local:** FFmpeg (imageio-ffmpeg), faster-whisper, edge-tts, gTTS
- **Frontend (optional):** Next.js, calls `/api/generate` to run pipeline

---

## 9. Example Output Structure

```
output/<run-name>/
  scene_plan.json
  scene_1.png, scene_2.png, ...
  scene_1.mp4, scene_2.mp4, ...
  voiceover.wav or voiceover.mp3
  final.mp4
  caption.txt
  hashtags.txt
```

---

## 10. Questions for ChatGPT / Workflow Improvement

When pasting this into ChatGPT, you could ask:

1. **How can we improve the scene planner prompts** to produce more professional, cinematic Reels? (Hook strength, visual_description quality, narrative structure)
2. **What’s a better workflow** for image and video generation? (Different models, upscaling, human curation, A/B prompts)
3. **How should we structure a “review” step** — e.g. regenerate only failed scenes, or allow manual prompt edits before Phase 4?
4. **What additions would make Reels feel more professional?** (Transitions, music, B-roll, branding, subtitle styling)
5. **What’s the optimal fallback order** for video models given reliability vs. quality tradeoffs?
6. **How can we reduce dependency on quota-limited APIs** (Gemini) while maintaining quality?
7. **Best practices for vertical short-form video** (pacing, text placement, hook length) that we can encode into prompts or config?

---

*Last updated: Feb 2025. Oasis MVP 0.1–0.2.*
