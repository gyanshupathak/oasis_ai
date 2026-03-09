# Oasis — Pipeline & Technical Deep Dive

> **Purpose:** Detailed pipeline flow, tech stack, and improvement levers for better Reel outputs.

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         INPUT: sample_post.txt (LinkedIn/Twitter)                │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  PHASE 1: Scene Planning (scene_planner.py)                                      │
│  ─────────────────────────────────────────────────────────────────────────────  │
│  • Gemini 2.5 Flash → JSON scene plan (scenes[], caption, hashtags)               │
│  • Fallback: gemini-2.5-flash-lite                                                │
│  • Retries: 429/503 with backoff                                                 │
│  • Output: scene_plan.json                                                        │
│                                                                                  │
│  Each scene: scene_id, purpose (HOOK|BUILD|PAYOFF), visual_description,          │
│              on_screen_text, voiceover, duration                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  PHASE 1.5: Overlay Planning (overlay_planner.py)                                 │
│  ─────────────────────────────────────────────────────────────────────────────  │
│  • Gemini per-scene → text position, timing, effect, logo                         │
│  • Fallback: gemini-2.5-flash-lite → sensible defaults (no LLM)                  │
│  • Output: plan["scenes"][i]["overlay"] enriched                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                    ┌───────────────────┴───────────────────┐
                    ▼                                       ▼
┌───────────────────────────────────────┐   ┌───────────────────────────────────────┐
│  PHASE 2: Image Gen (image_generator)  │   │  PHASE 3: Voiceover (voiceover.py)        │
│  ─────────────────────────────────── │   │  ─────────────────────────────────────── │
│  • Pollinations: klein → flux         │   │  • Gemini TTS → edge-tts → gTTS          │
│  • Prompt: "Vertical cinematic..."   │   │  • Voice: Puck (Gemini), Christopher     │
│    + visual_description + suffix      │   │    (edge)                                │
│  • Resolution: 576×1024 (9:16)        │   │  • Output: voiceover.wav (.mp3 fallback)  │
│  • Output: scene_1.png, scene_2.png   │   │                                          │
└───────────────────────────────────────┘   └───────────────────────────────────────┘
                    │                                       │
                    └───────────────────┬───────────────────┘
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  PHASE 4: Video Generation (video_generator.py)                                   │
│  ─────────────────────────────────────────────────────────────────────────────  │
│  • Seedance Lite (Pollinations I2V): upload image → prompt → 2–10s clip           │
│  • Image hosting: tmpfiles.org → 0x0.st → transfer.sh → catbox → imglink → file.io│
│  • Fallback: FFmpeg zoompan (image_to_clip) when Seedance fails                   │
│  • Output: scene_1.mp4, scene_2.mp4, ...                                         │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  PHASE 5: Assembly (video_assembler.py)                                           │
│  ─────────────────────────────────────────────────────────────────────────────  │
│  1. Concat all scene_N.mp4 → concat.mp4                                            │
│  2. Mux voiceover; if voiceover > max_duration → atempo (speed up) → 30s         │
│  3. Subtitle events: faster-whisper (phrase-level) or plan-based proportional     │
│  4. Apply time_scale to subtitles when voiceover was sped                         │
│  5. Burn ASS subtitles → final.mp4                                                │
│  6. Trim to max_duration_sec if specified                                         │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  PHASE 6: Packaging (output_packager.py)                                           │
│  ─────────────────────────────────────────────────────────────────────────────  │
│  • caption.txt, hashtags.txt from scene_plan                                       │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  OUTPUT: final.mp4, caption.txt, hashtags.txt                                      │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Phase-by-Phase Technical Detail

### Phase 1: Scene Planning

| Aspect | Detail |
|--------|--------|
| **Model** | `gemini-2.5-flash` → `gemini-2.5-flash-lite` |
| **Config** | `response_mime_type="application/json"`, temp=0.3 |
| **Input** | Post text, `reel_length`, `num_scenes`, `duration_per_scene` |
| **Output** | `total_duration`, `scenes[]`, `caption`, `hashtags` |

**Prompt logic:**
- Hook (Scene 1): Stop-the-scroll; rewrite for impact
- Build (2..n-1): One idea per scene; varied visuals
- Payoff: Memorable CTA

**visual_description** is the direct prompt for the image model → must be specific (lighting, angle, mood, style).

---

### Phase 1.5: Overlay Planning

| Aspect | Detail |
|--------|--------|
| **Model** | Same as Phase 1; 2 attempts per scene; fallback: defaults |
| **Per-scene** | `{ text: { show, content, position, start_time, end_time, effect }, logo: { enabled, position } }` |
| **Positions** | bottom-center, top-center, center, top-left, top-right, etc. |
| **Effects** | fade, slide, none |

---

### Phase 2: Image Generation

| Aspect | Detail |
|--------|--------|
| **Provider** | Pollinations.ai (`gen.pollinations.ai/image/{encoded_prompt}`) |
| **Models** | `klein` (FLUX.2 Klein) → `flux` fallback |
| **Resolution** | 576×1024 (config has 1024×1792 but Pollinations uses 576×1024) |
| **Prompt** | `"Vertical cinematic photograph. " + visual_description + " Soft lighting, shallow depth of field. Aspect ratio 9:16. High quality, professional."` |

**Gap:** Config `IMAGE_WIDTH×IMAGE_HEIGHT` (1024×1792) differs from Pollinations (576×1024). Assembly may scale.

---

### Phase 3: Voiceover

| Aspect | Detail |
|--------|--------|
| **Primary** | `gemini-2.5-flash-preview-tts`, voice "Puck" |
| **Fallback 1** | edge-tts (`en-US-ChristopherNeural`) → MP3 |
| **Fallback 2** | gTTS → MP3 |
| **Input** | Concatenated `voiceover` from all scenes |
| **Output** | WAV (Gemini) or MP3 (others) |

**Voice options:** Puck, Charon, Fenrir (male); Kore, Zephyr, Leda (female).

---

### Phase 4: Video Generation

| Aspect | Detail |
|--------|--------|
| **Primary** | Pollinations Seedance Lite I2V |
| **API** | `gen.pollinations.ai/image/{prompt}?model=seedance&duration=...&image={url}` |
| **Image upload** | 6 hosts tried in order; Pollinations needs HTTPS direct-download URL |
| **Prompt** | `"Portrait cinematic video. " + desc[:200] + ". Smooth motion, Instagram Reel style."` |
| **Duration** | Clamped 2–10s per scene |
| **Fallback** | FFmpeg `zoompan` + fade in/out on static image |

---

### Phase 5: Assembly

| Aspect | Detail |
|--------|--------|
| **Concat** | FFmpeg concat demuxer (scene_1.mp4 + scene_2.mp4 + ...) |
| **Mux** | Video + voiceover; voiceover normalized to `max_duration_sec` via atempo |
| **Subtitle source** | faster-whisper (`phrase_level=True`) or `build_voiceover_subtitle_events()` (plan-based) |
| **Subtitle format** | ASS; font 76px, outline 5, margin 80 |
| **Time scale** | When voiceover sped to 30s, subtitle timings × (30 / actual_dur) |

---

## 3. Key Constants (`config.py`, `video_assembler.py`)

| Constant | Value | Where |
|----------|-------|-------|
| MIN_SCENES, MAX_SCENES | 5 | config.py |
| MIN/MAX_SCENE_DURATION | 6 | config.py |
| MAX_ON_SCREEN_WORDS | 10 | config.py |
| IMAGE_WIDTH × HEIGHT | 1024×1792 | config.py |
| POLLINATIONS size | 576×1024 | image_generator.py |
| SUBTITLE_FONT_SIZE | 76 | video_assembler.py |
| SUBTITLE_OUTLINE | 5 | video_assembler.py |
| SUBTITLE_MARGIN_V | 80 | video_assembler.py |
| ZOOM_FACTOR | 1.1 | video_assembler.py |
| FADE_DURATION | 0.5 | video_assembler.py |

---

## 4. External Dependencies

| Dependency | Purpose |
|------------|---------|
| **google-genai** | Scene plan, overlay plan, TTS |
| **requests** | Pollinations, image hosts |
| **faster-whisper** | Audio → subtitle events |
| **edge-tts** | TTS fallback |
| **gtts** | TTS last resort |
| **imageio-ffmpeg** | FFmpeg binary (fallback) |
| **Pillow** | Image handling |

---

## 5. Improvement Levers for Better Outputs

### 5.1 Scene Planning (Phase 1)

| Lever | Current | Improvement |
|-------|---------|-------------|
| **Hook strength** | Prompt mentions "stop the scroll" | Add few-shot examples from best-performing Reels; A/B test hook templates |
| **visual_description** | 1–2 sentences, generic suffix | Add scene-type-specific suffixes (e.g. documentary vs corporate); avoid stock phrases |
| **Pacing** | Fixed 5–6 scenes | Allow 3–4 for punchy; 7–8 for educational |
| **Voiceover length** | "total speech ≈ reel_length" | Enforce word-count budget per scene to avoid voiceover overrun |

### 5.2 Image Quality (Phase 2)

| Lever | Current | Improvement |
|-------|---------|-------------|
| **Resolution** | 576×1024 | Use higher-res model or upscale post-gen |
| **Prompt** | Fixed prefix/suffix | Per-purpose prompts (hook vs build vs payoff) |
| **Model** | klein → flux | Add FLUX.1 Pro, SDXL, or Replicate alternatives |
| **Negative prompt** | None | Add "blurry, low quality, distorted" etc. if API supports |

### 5.3 Voiceover (Phase 3)

| Lever | Current | Improvement |
|-------|---------|-------------|
| **Voice** | Single (Puck/Christopher) | Make voice configurable; add female/male toggle |
| **Pacing** | Natural | Option to speed/slow to hit exact duration |
| **TTS fallback** | edge-tts, gTTS | Add ElevenLabs (paid) or OpenAI TTS for quality |

### 5.4 Video (Phase 4)

| Lever | Current | Improvement |
|-------|---------|-------------|
| **I2V** | Seedance only | Add Replicate minimax, Runway, Kling as fallbacks |
| **Image hosting** | 6 free hosts | Add S3/R2 with CDN for reliability |
| **FFmpeg fallback** | Zoom only | Add Ken Burns, parallax, or simple motion templates |

### 5.5 Assembly (Phase 5)

| Lever | Current | Improvement |
|-------|---------|-------------|
| **Transitions** | Hard cuts | Add crossfade, dissolve between scenes |
| **Subtitle style** | ASS, Arial 76px | Integrate presets (keyword_highlight, large_bold); configurable font/size |
| **Music** | None | Optional low-volume background track (royalty-free) |
| **On-screen overlays** | Not burned | Burn overlay text from overlay_planner into video |

### 5.6 Presets

`presets.py` has 5 presets (minimalist_dark, gradient_soft, documentary, etc.) with `visual`, `subtitle_style`, `background_color` — **not wired into CLI**. Wire these to `--preset` for consistent branding.

---

## 6. CLI Reference

```bash
python main.py --text sample_post.txt --length 30 --scenes 5 --name "my-reel" --frames 1
```

| Flag | Default | Description |
|------|---------|-------------|
| `--text` / `-t` | — | Post text or path to .txt |
| `--length` / `-l` | 30 | Reel length (seconds) |
| `--scenes` / `-s` | — | Number of scenes (with length → duration per scene) |
| `--no-voiceover` | — | Skip TTS |
| `--phase` / `-p` | — | Run up to phase N (1–6) |
| `--plan` | — | Use existing scene_plan.json |
| `--video-gen` | True | Use Seedance I2V |
| `--no-caption` | — | Skip Phase 6 |
| `--name` / `-n` | — | Output folder name |
| `--frames` / `-f` | 1 | Keyframes per scene (1 or 4) for I2V |

---

## 7. File Output Structure

```
output/<slug>/
├── scene_plan.json      # Full plan + overlays
├── scene_1.png ...      # Generated images
├── scene_1.mp4 ...     # Per-scene video clips
├── voiceover.wav       # TTS audio
├── final.mp4           # Assembled reel
├── caption.txt
└── hashtags.txt
```

---

## 8. Known Bottlenecks & Mitigations

| Bottleneck | Mitigation |
|------------|------------|
| **Gemini 429/503** | Retries added; consider caching scene plans; use flash-lite for overlays |
| **Seedance failures** | FFmpeg fallback; add Replicate/other I2V |
| **Image upload failures** | 6 hosts; consider persistent storage (S3) |
| **Voiceover > 30s** | Normalized via atempo; subtitles scaled |
| **Weak visuals** | Improve visual_description prompt; try different image models |

---

*Generated for Oasis workflow improvement. Feb 2025.*
