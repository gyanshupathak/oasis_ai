"""
Oasis MVP 0.2 - Style Presets
Each preset defines: visual strategy (minimal vs AI), subtitle style, background.
Default: minimalist_dark - gradient, keyword highlight, no AI (saves credits, premium feel).
"""

from typing import TypedDict


class PresetConfig(TypedDict):
    id: str
    label: str
    visual: str  # "gradient" | "gradient_soft" | "solid_dark" | "ai"
    subtitle_style: str  # "keyword_highlight" | "bold_hook" | "centered" | "large_bold" | "standard"
    background_color: str  # hex e.g. "#0a0a0a"
    background_color_end: str | None  # for gradient, end color; None = solid
    font_size: int
    font_size_hook: int | None  # None = same as font_size
    keyword_color: str | None  # hex for keyword highlight; None = no highlight
    outline: int


PRESETS: dict[str, PresetConfig] = {
    "minimalist_dark": {
        "id": "minimalist_dark",
        "label": "Minimalist Dark",
        "visual": "gradient",
        "subtitle_style": "keyword_highlight",
        "background_color": "#0a0a0a",
        "background_color_end": "#1a1a1a",
        "font_size": 78,
        "font_size_hook": 92,
        "keyword_color": "#f59e0b",  # amber
        "outline": 5,
    },
    "gradient_soft": {
        "id": "gradient_soft",
        "label": "Gradient Soft",
        "visual": "gradient_soft",
        "subtitle_style": "bold_hook",
        "background_color": "#1c1917",
        "background_color_end": "#292524",
        "font_size": 76,
        "font_size_hook": 88,
        "keyword_color": None,
        "outline": 4,
    },
    "documentary": {
        "id": "documentary",
        "label": "Documentary",
        "visual": "solid_dark",
        "subtitle_style": "centered",
        "background_color": "#0a0a0a",
        "background_color_end": None,
        "font_size": 74,
        "font_size_hook": None,
        "keyword_color": None,
        "outline": 4,
    },
    "cinematic": {
        "id": "cinematic",
        "label": "Cinematic (AI visuals)",
        "visual": "ai",
        "subtitle_style": "standard",
        "background_color": "#0a0a0a",
        "background_color_end": None,
        "font_size": 76,
        "font_size_hook": None,
        "keyword_color": None,
        "outline": 5,
    },
    "bold_fast": {
        "id": "bold_fast",
        "label": "Bold & Fast",
        "visual": "solid_dark",
        "subtitle_style": "large_bold",
        "background_color": "#171717",
        "background_color_end": None,
        "font_size": 84,
        "font_size_hook": 100,
        "keyword_color": "#fbbf24",
        "outline": 6,
    },
}

DEFAULT_PRESET = "minimalist_dark"


def is_minimal_preset(preset_id: str) -> bool:
    """True if preset uses gradient/solid (no AI images/video)."""
    cfg = PRESETS.get(preset_id, PRESETS[DEFAULT_PRESET])
    return cfg["visual"] in ("gradient", "gradient_soft", "solid_dark")
