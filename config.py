"""
Oasis MVP 0.1 - Configuration
Central place for constants. No magic numbers in the pipeline.
"""

import os
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# Scene constraints: 5 scenes, 6 sec each = 30 sec total
MIN_SCENES = 5
MAX_SCENES = 5
MIN_SCENE_DURATION = 6
MAX_SCENE_DURATION = 6
MAX_ON_SCREEN_WORDS = 10

# Video format
ASPECT_RATIO = "9:16"
IMAGE_WIDTH = 1024
IMAGE_HEIGHT = 1792

# Default reel length: 30 sec (6 x 5)
DEFAULT_REEL_LENGTH = 30

# Transition between scene clips (seconds). 0 = hard cut.
CROSSFADE_DURATION = 0.5

# Background music (optional). Add MP3 files: assets/music/{mood}.mp3 (calm, reflective, etc.)
MUSIC_DIR = PROJECT_ROOT / "assets" / "music"
MUSIC_VOLUME = 0.28  # Audible background; voiceover stays primary
