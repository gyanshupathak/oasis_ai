"""
Oasis MVP 0.1 - Phase 2: Image Generation
Uses Pollinations.ai. Fallback: klein → flux (best quality first).
"""

import os
import shutil
from pathlib import Path
from urllib.parse import quote

import requests

from config import OUTPUT_DIR

# Fixed prompt for cinematic consistency
IMAGE_PROMPT_PREFIX = "Vertical cinematic photograph. "
IMAGE_PROMPT_SUFFIX = " Soft lighting, shallow depth of field. Aspect ratio 9:16. High quality, professional."

# Image models: best → worst (Pollinations)
IMAGE_MODELS = ["klein", "flux"]
POLLINATIONS_WIDTH = 576
POLLINATIONS_HEIGHT = 1024  # 9:16 vertical


def _generate_image_with_prompt(
    prompt: str, output_path: Path, api_key: str, model: str = "klein"
) -> Path:
    """Generate single image from prompt. Internal helper."""
    encoded = quote(prompt, safe="")
    url = (
        f"https://gen.pollinations.ai/image/{encoded}"
        f"?model={model}"
        f"&width={POLLINATIONS_WIDTH}"
        f"&height={POLLINATIONS_HEIGHT}"
        f"&enhance=false"
    )
    r = requests.get(url, headers={"Authorization": f"Bearer {api_key}"}, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"Pollinations API error {r.status_code}: {r.text[:200]}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(r.content)
    return output_path


def generate_image(
    visual_description: str,
    scene_id: int,
    output_dir: Path = OUTPUT_DIR,
) -> Path:
    """
    Generate one image for a scene. Tries models in order: klein → flux.
    """
    api_key = os.environ.get("POLLINATIONS_API_KEY")
    if not api_key:
        raise ValueError(
            "POLLINATIONS_API_KEY not set in .env. "
            "Get free key at https://enter.pollinations.ai"
        )
    full_prompt = f"{IMAGE_PROMPT_PREFIX}{visual_description}{IMAGE_PROMPT_SUFFIX}"
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"scene_{scene_id}.png"
    last_err = None
    for model in IMAGE_MODELS:
        try:
            return _generate_image_with_prompt(full_prompt, out_path, api_key, model=model)
        except Exception as e:
            last_err = e
            if model != IMAGE_MODELS[-1]:
                print(f"  [Image] {model} failed, trying {IMAGE_MODELS[IMAGE_MODELS.index(model)+1]}...")
    raise last_err or RuntimeError("Image generation failed")


def generate_all_scene_images(
    scenes: list[dict],
    output_dir: Path = OUTPUT_DIR,
) -> list[Path]:
    """Generate one image per scene (legacy: for FFmpeg assembly)."""
    paths = []
    for scene in scenes:
        scene_id = scene.get("scene_id", len(paths) + 1)
        desc = scene.get("visual_description", "")
        if not desc:
            raise ValueError(f"Scene {scene_id} has no visual_description")
        path = generate_image(desc, scene_id, output_dir)
        paths.append(path)
    return paths


def _generate_image_with_model_fallback(prompt: str, path: Path, api_key: str) -> Path:
    """Try each image model until one succeeds."""
    last_err = None
    for model in IMAGE_MODELS:
        try:
            return _generate_image_with_prompt(prompt, path, api_key, model=model)
        except Exception as e:
            last_err = e
            if model != IMAGE_MODELS[-1]:
                next_m = IMAGE_MODELS[IMAGE_MODELS.index(model) + 1]
                print(f"  [Image] {model} failed, trying {next_m}...")
    raise last_err or RuntimeError("Image generation failed")


def generate_single_frames(
    scenes: list[dict],
    output_dir: Path = OUTPUT_DIR,
) -> list[tuple[Path, Path]]:
    """
    Generate one frame per scene (for I2V - Wan/minimax use 1 image).
    Returns list of (path, path) per scene - same path for compatibility.
    """
    api_key = os.environ.get("POLLINATIONS_API_KEY")
    if not api_key:
        raise ValueError(
            "POLLINATIONS_API_KEY not set in .env. "
            "Get free key at https://enter.pollinations.ai"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for i, scene in enumerate(scenes):
        scene_id = scene.get("scene_id", i + 1)
        desc = scene.get("visual_description", "")
        if not desc:
            raise ValueError(f"Scene {scene_id} has no visual_description")
        prompt = f"{IMAGE_PROMPT_PREFIX}{desc}. Cinematic key frame.{IMAGE_PROMPT_SUFFIX}"
        path = output_dir / f"scene_{scene_id}.png"
        _generate_image_with_model_fallback(prompt, path, api_key)
        results.append((path, path))  # same path (I2V uses only first frame)
    return results


def generate_four_frames_per_scene(
    scenes: list[dict],
    output_dir: Path = OUTPUT_DIR,
) -> list[tuple[Path, Path]]:
    """
    Generate 4 keyframes per scene (opening, early, late, closing).
    I2V models use 1 image - we use frame 1. Returns (path, path) for compatibility.
    """
    api_key = os.environ.get("POLLINATIONS_API_KEY")
    if not api_key:
        raise ValueError(
            "POLLINATIONS_API_KEY not set in .env. "
            "Get free key at https://enter.pollinations.ai"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    suffixes = [
        "opening shot, beginning",
        "early moment, establishing",
        "late moment, building",
        "closing shot, resolution",
    ]
    for i, scene in enumerate(scenes):
        scene_id = scene.get("scene_id", i + 1)
        desc = scene.get("visual_description", "")
        if not desc:
            raise ValueError(f"Scene {scene_id} has no visual_description")
        paths = []
        for j, suf in enumerate(suffixes):
            prompt = f"{IMAGE_PROMPT_PREFIX}{desc}. {suf}. Cinematic key frame.{IMAGE_PROMPT_SUFFIX}"
            path = output_dir / f"scene_{scene_id}_f{j+1}.png"
            _generate_image_with_model_fallback(prompt, path, api_key)
            paths.append(path)
        # I2V uses first frame; also write scene_N.png as primary for compatibility
        primary = output_dir / f"scene_{scene_id}.png"
        shutil.copy2(paths[0], primary)
        results.append((primary, primary))
    return results


def generate_start_end_frames(
    scenes: list[dict],
    output_dir: Path = OUTPUT_DIR,
) -> list[tuple[Path, Path]]:
    """
    Generate start + end frame for each scene (legacy: for interpolation).
    Returns list of (start_path, end_path) per scene.
    """
    api_key = os.environ.get("POLLINATIONS_API_KEY")
    if not api_key:
        raise ValueError(
            "POLLINATIONS_API_KEY not set in .env. "
            "Get free key at https://enter.pollinations.ai"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for i, scene in enumerate(scenes):
        scene_id = scene.get("scene_id", i + 1)
        desc = scene.get("visual_description", "")
        if not desc:
            raise ValueError(f"Scene {scene_id} has no visual_description")
        start_prompt = f"{IMAGE_PROMPT_PREFIX}{desc}. Opening shot, beginning of scene. Static moment.{IMAGE_PROMPT_SUFFIX}"
        end_prompt = f"{IMAGE_PROMPT_PREFIX}{desc}. Closing shot, end of scene. Resolution moment.{IMAGE_PROMPT_SUFFIX}"
        start_path = output_dir / f"scene_{scene_id}_start.png"
        end_path = output_dir / f"scene_{scene_id}_end.png"
        _generate_image_with_model_fallback(start_prompt, start_path, api_key)
        _generate_image_with_model_fallback(end_prompt, end_path, api_key)
        results.append((start_path, end_path))
    return results
