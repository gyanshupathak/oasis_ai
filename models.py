"""
Oasis MVP 0.1 - Data Models
Locked schema for scene_plan.json. Do not change unless necessary.
"""

from typing import TypedDict


class TextOverlay(TypedDict, total=False):
    show: bool
    content: str
    position: str  # bottom-center, top-center, center, etc.
    start_time: float
    end_time: float
    effect: str  # fade, slide, none


class LogoOverlay(TypedDict, total=False):
    enabled: bool
    position: str  # top-right, top-left, etc.


class Overlay(TypedDict, total=False):
    text: TextOverlay
    logo: LogoOverlay


class Scene(TypedDict):
    scene_id: int
    purpose: str  # e.g. "Hook", "Conflict", "Resolution"
    visual_description: str
    on_screen_text: str  # max 10 words
    voiceover: str
    duration: int  # seconds
    overlay: Overlay  # Added by AI overlay planner (Phase 1.5)


class ScenePlan(TypedDict):
    total_duration: int
    scenes: list[Scene]
    caption: str
    hashtags: list[str]
