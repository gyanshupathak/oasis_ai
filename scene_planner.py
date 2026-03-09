"""
Oasis MVP 0.1 - Phase 1: Scene Planning Engine
Converts LinkedIn/Twitter post → structured scene_plan.json (scenes with purpose, voiceover, etc.).
Uses Gemini (free tier). Falls back to gemini-1.5-flash if 2.5-flash quota exceeded.
API key: https://aistudio.google.com/apikey
"""

import json
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import ClientError, ServerError

from config import (
    DEFAULT_REEL_LENGTH,
    MAX_ON_SCREEN_WORDS,
    MAX_SCENE_DURATION,
    MAX_SCENES,
    MIN_SCENE_DURATION,
    MIN_SCENES,
)
from models import ScenePlan

load_dotenv()

# Primary and fallback models (separate quotas on free tier)
# gemini-1.5-flash returns 404 NOT_FOUND; use 2.5-flash-lite (1000 req/day)
SCENE_PLANNER_MODEL = "gemini-2.5-flash"
SCENE_PLANNER_FALLBACK = "gemini-2.5-flash-lite"


def _parse_llm_json(raw: str) -> dict:
    """
    Parse JSON from LLM response. Handles markdown code blocks, trailing commas,
    and other common issues.
    """
    text = raw.strip()
    if not text:
        raise ValueError("Empty response from LLM")

    # Remove BOM and other leading invisible chars
    text = text.lstrip("\ufeff\ufffe")

    # Strip markdown code blocks
    if "```" in text:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            text = match.group(1).strip()

    # Remove trailing commas before ] or } (invalid in JSON)
    text = re.sub(r",\s*([}\]])", r"\1", text)

    def _try_load(s: str):
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            return None

    result = _try_load(text)
    if result is not None:
        return result

    # Repair unquoted keys (e.g. scene_id: 1 → "scene_id": 1) — only after { or ,
    repaired = re.sub(r'([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', text)
    result = _try_load(repaired)
    if result is not None:
        return result

    # Try extracting first complete { ... } object
    depth = 0
    start = -1
    for i, c in enumerate(text):
        if c == "{":
            if depth == 0:
                start = i
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                chunk = text[start : i + 1]
                result = _try_load(chunk)
                if result is not None:
                    return result
                chunk_repaired = re.sub(r'([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', chunk)
                result = _try_load(chunk_repaired)
                if result is not None:
                    return result

    try:
        json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON from LLM: {e}") from e


def generate_scenes(
    linkedin_text: str,
    reel_length: int = DEFAULT_REEL_LENGTH,
    voiceover_on: bool = True,
    num_scenes: int | None = None,
    duration_per_scene: int | None = None,
) -> ScenePlan:
    """
    Convert LinkedIn/Twitter post text into a structured scene plan for a Reel.
    Uses Google Gemini (free API key at aistudio.google.com/apikey).
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in .env. Get free key at https://aistudio.google.com/apikey")

    client = genai.Client(api_key=api_key)

    min_s, max_s = (num_scenes, num_scenes) if num_scenes else (MIN_SCENES, MAX_SCENES)
    min_d, max_d = (duration_per_scene, duration_per_scene) if duration_per_scene else (MIN_SCENE_DURATION, MAX_SCENE_DURATION)

    system_prompt = f"""You are an expert cinematic video narrative planner for professional Instagram Reels.
Convert a LinkedIn or Twitter post into a high-quality Reel plan that keeps viewers watching.

RULES (STRICT):
- Total scenes: {min_s} to {max_s}
- Each scene duration: {min_d} to {max_d} seconds (distribute evenly; total ≤ {reel_length}s)
- On-screen text per scene: maximum {MAX_ON_SCREEN_WORDS} words (only when it adds impact)
- Vertical video 9:16 — every visual must work in portrait
- Output valid JSON only. No prose, no markdown, no explanation.

NARRATIVE STRUCTURE (professional pacing):
- Scene 1 (HOOK): Stop the scroll. Bold claim, surprising stat, or provocative question. 3–5 seconds max.
- Scenes 2–{max(2, max_s - 1)} (BUILD): Unpack the post’s main points. One idea per scene. Vary visuals.
- Final scene (PAYOFF): Memorable takeaway or call-to-action. Leave them thinking.

CRITICAL — VIRAL HOOK (Scene 1 voiceover):
Generate a scroll-stopping hook. NEVER use the post's first line verbatim.
- Use pattern interrupt: surprising contrast, bold claim, or curiosity gap
- Be specific: numbers, names, concrete details beat vague intros
- Examples: "The exact day you got older had nothing to do with your birthday." / "A $90B CEO does customer support for 15 minutes every day. Here's why."
- Avoid: "Most people don't realize..." / "Here's what I learned..." — too generic

CRITICAL — CONTEXT & CONTINUITY (scenes 2 to {max(2, max_s)}):
Each scene must flow from the previous. Maintain context across the reel:
- visual_description: Use consistent lighting/style (e.g. same "soft diffused" or "cinematic" across scenes)
- Narrative bridge: Scene N+1 should naturally follow from Scene N — no jarring topic jumps
- Visual flow: If Scene 1 is close-up, Scene 2 could pull to medium; build rhythm (close → wide → close)

CRITICAL — visual_description (for AI video generation):
Each visual_description is the DIRECT PROMPT for the image-to-video model. Be HIGHLY detailed and specific. Write 2-4 sentences covering ALL of:

1. SUBJECT & SETTING (required):
   - Who/what: "A woman in her 40s", "CEO at standing desk", "empty gym at dawn"
   - Where: "modern minimalist office", "rain-slicked city street", "sunlit kitchen"
   - Props/objects that tell the story: "wrinkled marathon bib", "old photo album", "empty chair"

2. LIGHTING (required):
   - Type: soft diffused, golden hour, dramatic side-light, cool blue morning, warm tungsten, overcast natural
   - Direction: "light from left", "backlit silhouette", "face half in shadow"
   - Quality: "harsh midday sun", "diffused through curtains", "studio key light"

3. CAMERA & FRAMING (required):
   - Shot size: close-up face, medium shot waist-up, wide establishing, extreme close-up on hands
   - Angle: low angle (powerful), high angle (vulnerable), eye level, Dutch tilt
   - Movement: "slow zoom in", "static locked-off", "subtle handheld sway", "dolly forward"

4. STYLE & MOOD (required):
   - Style: cinematic, documentary verité, corporate clean, editorial fashion, indie film
   - Mood: confident, urgent, reflective, nostalgic, hopeful, tense
   - Color tone: desaturated, warm sepia, cold blue, high contrast black-and-white

5. MOTION HINTS (for I2V):
   - "subject slowly turns head", "breathing visibly", "hands clasped", "camera slowly pushes in"
   - Avoid: generic "person standing" — add micro-movements or environmental motion

BAD (generic): "Person in office looking thoughtful."
GOOD: "Woman in her early 40s at a minimalist desk, morning light from window left casting soft shadow. Medium shot, eye level. She looks at an old photograph, hands resting. Cinematic documentary style, warm color grade, shallow depth of field. Subtle slow zoom in. Reflective, nostalgic mood."
"""

    user_prompt = f"""Convert this post into a Reel scene plan:

Target total duration: {reel_length} seconds (voiceover must fit within this — keep each scene's voiceover concise so total speech ≈ {reel_length}s)
Include voiceover: {voiceover_on}

POST:
---
{linkedin_text}
---

Return a JSON object with: total_duration, scenes (array of scene objects), caption, hashtags, music_mood.
Each scene must have: scene_id, purpose, visual_description, on_screen_text, voiceover, duration.

music_mood (required): One word describing the background music that should accompany this post. Choose from: calm, reflective, inspiring, hopeful, urgent, nostalgic, ambient, motivational. Pick the mood that best matches the post's tone.

For each scene, write a DETAILED 2-4 sentence visual_description covering subject, setting, lighting, camera, style, mood, and motion. Pass directly to the video model."""

    contents = f"{system_prompt}\n\n{user_prompt}"
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.3,
    )

    def _call(model: str):
        return client.models.generate_content(model=model, contents=contents, config=config)

    def _parse_retry_seconds(err: Exception) -> int:
        msg = str(err)
        if "503" in msg:
            return 20  # High demand, often clears quickly
        m = re.search(r"retry in (\d+(?:\.\d+)?)s", msg, re.I) or re.search(r"retryDelay[:\s]+(\d+)", msg)
        if m:
            return min(120, max(30, int(float(m.group(1)))))
        return 60

    last_err = None
    response = None
    for model in [SCENE_PLANNER_MODEL, SCENE_PLANNER_FALLBACK]:
        for attempt in range(3):
            try:
                response = _call(model)
                break
            except (ClientError, ServerError) as e:
                last_err = e
                code = getattr(e, "code", None) or getattr(e, "status_code", None)
                is_retryable = code in (429, 503) or "429" in str(e) or "503" in str(e)
                if is_retryable:
                    wait = _parse_retry_seconds(e)
                    if attempt < 2:
                        reason = "High demand (503)" if code == 503 else "Quota/rate limit"
                        print(f"  [Gemini] {reason}, retrying in {wait}s...")
                        time.sleep(wait)
                        continue
                    if model == SCENE_PLANNER_MODEL:
                        print(f"  [Gemini] {model} quota exceeded, trying {SCENE_PLANNER_FALLBACK}...")
                    break
                raise
        else:
            continue
        if response is not None:
            break
    if response is None:
        raise last_err or RuntimeError("Scene planning failed")

    raw = response.text
    plan = _parse_llm_json(raw)

    # Validate minimum structure
    if "scenes" not in plan or not plan["scenes"]:
        raise ValueError("LLM returned invalid plan: no scenes")
    if "total_duration" not in plan:
        plan["total_duration"] = sum(s.get("duration", 4) for s in plan["scenes"])
    if "caption" not in plan:
        plan["caption"] = ""
    if "hashtags" not in plan:
        plan["hashtags"] = []
    if "music_mood" not in plan:
        plan["music_mood"] = "ambient"

    # Normalize scene_id, duration, required fields
    for i, scene in enumerate(plan["scenes"]):
        if "scene_id" in scene:
            scene_id = scene["scene_id"]
            if isinstance(scene_id, str) and scene_id.startswith("scene_"):
                scene["scene_id"] = int(scene_id.replace("scene_", ""))
            elif isinstance(scene_id, str) and scene_id.isdigit():
                scene["scene_id"] = int(scene_id)
            elif not isinstance(scene_id, int):
                scene["scene_id"] = i + 1
        else:
            scene["scene_id"] = i + 1

        # Normalize duration to int, clamp to allowed range
        d = scene.get("duration", min_d)
        scene["duration"] = max(min_d, min(max_d, int(float(d))))

        # Ensure required string fields exist
        scene.setdefault("purpose", "")
        scene.setdefault("visual_description", "")
        scene.setdefault("on_screen_text", "")
        scene.setdefault("voiceover", "")

    plan["total_duration"] = int(sum(s["duration"] for s in plan["scenes"]))
    return plan

def save_scene_plan(plan: ScenePlan, path: Path) -> None:
    """Write scene plan to JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)

def load_scene_plan(path: Path) -> ScenePlan:
    """Load scene plan from JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

if __name__ == "__main__":
    test_post = """
    I spent 3 years building a startup. Failed twice. On the third try, we hit $1M ARR.
    Here's what I learned about persistence that nobody talks about:
    1. Failure is data, not defeat
    2. Your network compounds slowly
    3. The best founders are boring for 5 years, then overnight successes
    """
    plan = generate_scenes(test_post.strip(), reel_length=45, voiceover_on=True)
    print(json.dumps(plan, indent=2))
    save_scene_plan(plan, Path("output/scene_plan.json"))
    print("\n✅ Saved to output/scene_plan.json")
