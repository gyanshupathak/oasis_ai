"""
Oasis MVP 0.1 - AI Background Music Generation
Uses Pollinations ElevenLabs Music (free, same key as images/video). Mood-matched to post.
"""

import os
from pathlib import Path
from urllib.parse import quote

import requests

# Mood → music description for ElevenLabs Music (instrumental, fits short-form video)
MOOD_PROMPTS = {
    "calm": "calm ambient piano, soft, relaxing, minimalist, background music for video",
    "reflective": "reflective, thoughtful, slow piano, contemplative, emotional",
    "inspiring": "inspiring, uplifting, gentle strings and piano, hopeful",
    "hopeful": "hopeful, positive, soft acoustic, gentle melody",
    "urgent": "urgent, driving, subtle tension, corporate, background",
    "nostalgic": "nostalgic, warm, bittersweet, soft piano, memories",
    "ambient": "ambient, atmospheric, soft pads, subtle, background music",
    "motivational": "motivational, uplifting, energetic but soft, inspiring",
}


def _mood_to_prompt(mood: str) -> str:
    """Convert music_mood to music generation prompt."""
    m = (mood or "ambient").lower().strip()
    return MOOD_PROMPTS.get(m, MOOD_PROMPTS["ambient"])


def generate_background_music(
    mood: str,
    duration_sec: float,
    output_path: Path,
) -> Path | None:
    """
    Generate background music via Pollinations ElevenLabs Music (gen.pollinations.ai).
    Uses POLLINATIONS_API_KEY (same as images/video). Free on Seed tier.
    Returns output_path on success, None on failure.
    """
    api_key = os.environ.get("POLLINATIONS_API_KEY")
    if not api_key:
        return None

    prompt = _mood_to_prompt(mood)
    duration = min(max(8, int(duration_sec)), 300)  # 3-300s per API
    encoded = quote(prompt, safe="")

    url = (
        f"https://gen.pollinations.ai/audio/{encoded}"
        f"?model=elevenmusic"
        f"&duration={duration}"
        f"&instrumental=true"
    )

    try:
        r = requests.get(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=120,
        )
        if r.status_code == 200 and r.content:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(r.content)
            return output_path
    except Exception:
        pass
    return None
