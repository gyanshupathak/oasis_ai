"""
Oasis MVP 0.1 - Phase 1.5: AI Overlay Planner
Analyzes each scene and decides: text placement, timing, effects, logo.
Uses Gemini. Fallback: gemini-2.5-flash-lite. Last resort: sensible defaults.
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

load_dotenv()

# Best → worst: flash (richer) → flash-lite (separate quota)
OVERLAY_MODELS = ["gemini-2.5-flash", "gemini-2.5-flash-lite"]


def _get_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in .env")
    return genai.Client(api_key=api_key)


def plan_overlays(plan: dict) -> dict:
    """
    For each scene, call AI to decide text/logo overlay: position, timing, effect.
    Merges overlay config into each scene under key "overlay".
    """
    scenes = plan.get("scenes", [])
    if not scenes:
        return plan

    client = _get_client()

    system_prompt = """You are an overlay planner for short-form video.
Given a scene's visual description, voiceover, and on-screen text, decide how to display the text.

Rules:
- Vertical video 9:16. Safe zones: avoid center if face/important element there.
- Positions: "bottom-center", "top-center", "center", "top-left", "top-right", "bottom-left", "bottom-right"
- Timing: start_time and end_time in seconds within the scene (0 to duration).
- Effects: "fade" (fade in/out), "slide" (slide from bottom), "none" (instant appear)
- Text: use on_screen_text if it adds value; set show=false if redundant with voiceover.
- Logo: set enabled=true only for build/payoff scenes, false for hook (too busy).
- Logo position: "top-right", "top-left", "bottom-right", "bottom-left"

Output valid JSON only. No prose."""

    for i, scene in enumerate(scenes):
        scene_id = scene.get("scene_id", i + 1)
        duration = float(scene.get("duration", 6))
        visual = scene.get("visual_description", "")
        voiceover = scene.get("voiceover", "")
        on_screen = scene.get("on_screen_text", "")
        purpose = scene.get("purpose", "")

        user_prompt = f"""Scene {scene_id} (duration {duration}s):
- Purpose: {purpose}
- Visual: {visual}
- Voiceover: {voiceover}
- On-screen text: {on_screen}

Return JSON:
{{
  "text": {{
    "show": true/false,
    "content": "exact text to display or empty",
    "position": "bottom-center|top-center|center|top-left|top-right|bottom-left|bottom-right",
    "start_time": 0.5,
    "end_time": {duration - 0.5},
    "effect": "fade|slide|none"
  }},
  "logo": {{
    "enabled": true/false,
    "position": "top-right|top-left|bottom-right|bottom-left"
  }}
}}"""

        overlay = None
        last_err = None
        for model in OVERLAY_MODELS:
            for attempt in range(2):
                try:
                    response = client.models.generate_content(
                        model=model,
                        contents=f"{system_prompt}\n\n{user_prompt}",
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.2,
                        ),
                    )
                    raw = response.text
                    overlay = json.loads(raw)
                    break
                except (ClientError, ServerError) as e:
                    last_err = e
                    code = getattr(e, "code", None) or getattr(e, "status_code", None)
                    is_retryable = code in (429, 503) or "429" in str(e) or "503" in str(e)
                    if is_retryable and attempt < 1:
                        wait = 15 if code == 503 else (30 if "429" in str(e) else 15)
                        print(f"  [Overlay] API {code or 'error'}, retrying in {wait}s...")
                        time.sleep(wait)
                        continue
                    if is_retryable:
                        break  # try next model
                    raise
            if overlay is not None:
                break

        if overlay is None:
            # Last resort: sensible defaults (no LLM)
            overlay = {
                "text": {
                    "show": bool(on_screen.strip()),
                    "content": on_screen.strip(),
                    "position": "bottom-center",
                    "start_time": 0.5,
                    "end_time": max(0.5, duration - 0.5),
                    "effect": "fade",
                },
                "logo": {"enabled": False, "position": "top-right"},
            }

        # Validate and clamp text overlay
        t = overlay.get("text", {})
        if t.get("show") and not t.get("content"):
            t["content"] = on_screen.strip()
            t["show"] = bool(t["content"])
        t["start_time"] = max(0.0, min(float(t.get("start_time", 0.5)), duration))
        t["end_time"] = max(t["start_time"], min(float(t.get("end_time", duration)), duration))
        t["position"] = t.get("position", "bottom-center")
        if t["position"] not in (
            "bottom-center", "top-center", "center",
            "top-left", "top-right", "bottom-left", "bottom-right"
        ):
            t["position"] = "bottom-center"
        t["effect"] = t.get("effect", "fade")
        if t["effect"] not in ("fade", "slide", "none"):
            t["effect"] = "fade"

        # Validate logo overlay
        logo = overlay.get("logo", {})
        logo["enabled"] = bool(logo.get("enabled", False))
        logo["position"] = logo.get("position", "top-right")
        if logo["position"] not in ("top-right", "top-left", "bottom-right", "bottom-left"):
            logo["position"] = "top-right"

        scene["overlay"] = overlay

    return plan
