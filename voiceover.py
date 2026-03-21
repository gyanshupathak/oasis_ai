"""
Oasis MVP 0.1 - Phase 3: Voiceover
Uses Gemini 2.5 Flash Preview TTS. Fallback to edge-tts when quota exhausted.
"""

import asyncio
import wave
from pathlib import Path

from dotenv import load_dotenv

from config import OUTPUT_DIR

load_dotenv()

# Male voices: Puck, Charon, Fenrir, Orus, etc. Female: Kore, Zephyr, Leda, etc.
DEFAULT_VOICE = "Puck"
# edge-tts voice (used when Gemini TTS quota exceeded)
EDGE_TTS_VOICE = "en-US-ChristopherNeural"


def _generate_voiceover_gemini(
    full_text: str,
    output_path: Path,
    voice_name: str,
) -> Path:
    """Generate audio via Gemini TTS. Raises on 429 or other errors."""
    import os
    import base64
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY not set in .env. "
            "Get free key at https://aistudio.google.com/apikey"
        )
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.5-flash-preview-tts",
        contents=full_text,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=voice_name,
                    )
                )
            ),
        ),
    )
    if not response.candidates or not response.candidates[0].content.parts:
        raise ValueError("Gemini TTS did not return audio")
    part = response.candidates[0].content.parts[0]
    if part.inline_data is None:
        raise ValueError("Gemini TTS did not return audio")
    pcm_data = part.inline_data.data
    if isinstance(pcm_data, str):
        pcm_data = base64.b64decode(pcm_data)
    with wave.open(str(output_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(pcm_data)
    return output_path


def _generate_voiceover_edge_tts(full_text: str, output_path: Path) -> Path:
    """Generate audio via edge-tts (free, no quota). Output: MP3."""
    import edge_tts

    mp3_path = output_path.with_suffix(".mp3") if output_path.suffix == ".wav" else output_path
    async def _run():
        communicate = edge_tts.Communicate(full_text, EDGE_TTS_VOICE)
        await communicate.save(str(mp3_path))
    asyncio.run(_run())
    return mp3_path


def _generate_voiceover_gtts(full_text: str, output_path: Path) -> Path:
    """Generate audio via gTTS (free, no quota). Output: MP3. Last resort."""
    try:
        from gtts import gTTS
    except ImportError:
        raise ImportError("pip install gtts for gTTS TTS fallback")
    mp3_path = output_path.with_suffix(".mp3") if output_path.suffix == ".wav" else output_path
    tts = gTTS(text=full_text, lang="en", slow=False)
    tts.save(str(mp3_path))
    return mp3_path


def generate_voiceover(
    full_text: str,
    output_path: Path | None = None,
    voice_name: str = DEFAULT_VOICE,
) -> Path:
    """
    Generate audio from text.
    Tries Gemini TTS first; on failure (quota, 5xx, or other errors) falls back to
    edge-tts, then gTTS as last resort.
    Output: WAV (Gemini) or MP3 (edge-tts / gTTS). FFmpeg accepts both.
    """
    output_path = output_path or OUTPUT_DIR / "voiceover.wav"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # TTS fallback chain: Gemini TTS → edge-tts → gTTS (best → worst)
    try:
        return _generate_voiceover_gemini(full_text, output_path, voice_name)
    except Exception as e:
        err_str = str(e).lower()
        if "429" in err_str or "resource_exhausted" in err_str or "quota" in err_str:
            print("  [Voiceover] Gemini TTS quota exceeded, trying edge-tts...")
        else:
            print("  [Voiceover] Gemini TTS failed, trying edge-tts...")
        try:
            return _generate_voiceover_edge_tts(full_text, output_path)
        except Exception:
            print("  [Voiceover] edge-tts failed, using gTTS fallback...")
            return _generate_voiceover_gtts(full_text, output_path)


def build_voiceover_from_plan(plan: dict, voiceover_on: bool = True) -> tuple[str, list[dict]]:
    """
    Concatenate scene voiceovers and build timing map.
    """
    scenes = plan.get("scenes", [])
    if not voiceover_on or not scenes:
        return "", []

    parts = []
    timings = []
    offset = 0.0

    for scene in scenes:
        text = scene.get("voiceover", "").strip()
        duration = float(scene.get("duration", 4))
        parts.append(text)
        timings.append({
            "scene_id": scene.get("scene_id"),
            "start": offset,
            "end": offset + duration,
            "duration": duration,
        })
        offset += duration

    full_text = " ".join(parts)
    return full_text, timings


def _split_into_phrases(text: str) -> list[str]:
    """
    Split voiceover into phrase-level chunks for subtitle display.
    Splits on sentence boundaries (.!?) and commas; no gaps.
    """
    import re
    if not text.strip():
        return []
    parts = re.split(r"(?<=[.!?])\s+|\s*,\s*", text.strip())
    phrases = [p.strip() for p in parts if p.strip()]
    if not phrases:
        return [text.strip()]
    return phrases


def word_events_to_sliding_window(
    word_events: list[dict],
    max_words: int = 4,
) -> list[dict]:
    """
    Legacy: sliding window. Use word_events_to_batched_display for the standard behavior.
    """
    if not word_events:
        return []
    window: list[str] = []
    out = []
    for ev in word_events:
        word = (ev.get("text") or "").strip()
        if not word:
            continue
        window.append(word)
        if len(window) > max_words:
            window.pop(0)
        out.append({
            "text": " ".join(window),
            "start": ev["start"],
            "end": ev["end"],
        })
    return out


def word_events_to_batched_display(
    word_events: list[dict],
    max_words: int = 4,
    hold_after_batch: float = 0.15,
) -> list[dict]:
    """
    Batch display: word 1 appears, then 1+2, then 1+2+3, then 1+2+3+4. All disappear.
    Then word 5, 5+6, 5+6+7, 5+6+7+8. Repeat.
    Events are sequential (not overlapping) so each replaces the previous on screen.
    """
    if not word_events:
        return []
    words = [ev for ev in word_events if (ev.get("text") or "").strip()]
    if not words:
        return []

    out = []
    i = 0
    while i < len(words):
        batch = words[i : i + max_words]
        clear_time = batch[-1]["end"] + hold_after_batch
        if i + max_words < len(words):
            clear_time = min(clear_time, words[i + max_words]["start"] - 0.05)

        for j in range(len(batch)):
            accumulated = " ".join(b["text"].strip() for b in batch[: j + 1])
            # Sequential: each event ends when next starts (or at clear for last)
            if j + 1 < len(batch):
                end_t = batch[j + 1]["start"]
            else:
                end_t = clear_time
            out.append({
                "text": accumulated,
                "start": batch[j]["start"],
                "end": end_t,
            })
        i += len(batch)
    return out


def get_subtitle_events_from_audio(
    audio_path: Path,
    phrase_level: bool = True,
) -> list[dict]:
    """
    Transcribe audio with faster-whisper and return subtitle events.
    phrase_level=True: segments (phrases) appear when spoken, then disappear.
    phrase_level=False: word-by-word (one word at a time).
    Returns list of {"text": str, "start": float, "end": float}.
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return []

    if not audio_path.exists():
        return []

    try:
        model = WhisperModel("base", device="cpu", compute_type="int8")
        segments, _ = model.transcribe(
            str(audio_path),
            word_timestamps=not phrase_level,
        )
        events = []

        if phrase_level:
            for seg in segments:
                text = (seg.text or "").strip()
                if text:
                    events.append({
                        "text": text,
                        "start": seg.start,
                        "end": seg.end,
                    })
        else:
            for seg in segments:
                words = getattr(seg, "words", None) or []
                if not words:
                    text = (seg.text or "").strip()
                    if text:
                        events.append({"text": text, "start": seg.start, "end": seg.end})
                    continue
                for w in words:
                    word = (w.word or "").strip()
                    if word:
                        events.append({"text": word, "start": w.start, "end": w.end})
        return events
    except Exception:
        return []


def build_voiceover_subtitle_events(
    plan: dict,
    actual_audio_duration: float | None = None,
    word_level: bool = False,
) -> list[dict]:
    """
    Build subtitle events: phrase-level (split on .!?, and commas), proportional timing.
    word_level=True: split into words for sliding-window display.
    Fallback when audio transcription is not available.
    If actual_audio_duration is provided, scales events to match real TTS timing.
    Returns list of {"text": str, "start": float, "end": float}.
    """
    events = []
    offset = 0.0
    planned_dur = 0.0
    for scene in plan.get("scenes", []):
        voiceover = scene.get("voiceover", "").strip()
        duration = float(scene.get("duration", 4))

        if not voiceover:
            offset += duration
            planned_dur += duration
            continue

        phrases = _split_into_phrases(voiceover)
        if not phrases:
            offset += duration
            planned_dur += duration
            continue

        phrase_dur = duration / len(phrases)
        t = offset
        for p in phrases:
            text = p.strip()
            if text:
                if word_level:
                    words = text.split()
                    w_dur = phrase_dur / max(1, len(words))
                    for i, w in enumerate(words):
                        if w:
                            events.append({
                                "text": w,
                                "start": t + i * w_dur,
                                "end": t + (i + 1) * w_dur,
                            })
                else:
                    events.append({
                        "text": text,
                        "start": t,
                        "end": t + phrase_dur,
                    })
            t += phrase_dur
        offset += duration
        planned_dur += duration

    if not events or actual_audio_duration is None or actual_audio_duration <= 0.1:
        return events
    if planned_dur <= 0.1:
        return events

    scale = actual_audio_duration / planned_dur
    for ev in events:
        ev["start"] *= scale
        ev["end"] *= scale
    return events


def build_onscreen_text_events(plan: dict) -> list[dict]:
    """
    Build subtitle events from scene planner's on_screen_text.
    Uses overlay start_time/end_time when available, else full scene duration.
    Returns list of {"text": str, "start": float, "end": float}.
    """
    events = []
    offset = 0.0

    for scene in plan.get("scenes", []):
        duration = float(scene.get("duration", 4))
        text = (
            (scene.get("overlay") or {}).get("text") or {}
        ).get("content") or scene.get("on_screen_text", "").strip()

        if not text:
            offset += duration
            continue

        overlay = scene.get("overlay") or {}
        text_cfg = overlay.get("text") or {}
        if text_cfg.get("show") is False:
            offset += duration
            continue

        start = offset + max(0, float(text_cfg.get("start_time", 0)))
        end = offset + min(duration, float(text_cfg.get("end_time", duration)))
        if end <= start:
            end = start + 0.5

        events.append({"text": text, "start": start, "end": end})
        offset += duration

    return events
