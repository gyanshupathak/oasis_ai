"""
Oasis MVP 0.1 - Phase 4: Video Generation
Seedance Lite (Pollinations I2V) -> Grok (Pollinations T2V) -> FFmpeg fallback.
"""

import os
from pathlib import Path
from urllib.parse import quote

import requests

from config import OUTPUT_DIR
from video_assembler import image_to_clip

POLLINATIONS_SEEDANCE = "seedance"
POLLINATIONS_GROK_VIDEO = "grok-video"
MAX_PROMPT_CHARS = 200


def _to_direct_image_url(url: str) -> str:
    """
    Convert tmpfiles.org page URL to direct download URL.
    tmpfiles returns https://tmpfiles.org/xxx but Pollinations needs raw image at https://tmpfiles.org/dl/xxx.
    """
    if "tmpfiles.org/" in url and "/dl/" not in url:
        return url.replace("tmpfiles.org/", "tmpfiles.org/dl/", 1)
    return url


def _upload_for_url(file_path: Path) -> str | None:
    """
    Upload file to get public URL. Tries multiple hosts.
    Returns None if all fail (Pollinations requires HTTPS URL, not base64).
    Uses direct-download URLs where needed (e.g. tmpfiles.org/dl/).
    """
    with open(file_path, "rb") as f:
        data = f.read()
    for name, fn in [
        ("tmpfiles.org", lambda: _try_tmpfiles(file_path.name, data)),
        ("0x0.st", lambda: _try_0x0_st(file_path.name, data)),
        ("transfer.sh", lambda: _try_transfer_sh(file_path.name, data)),
        ("litterbox.catbox.moe", lambda: _try_catbox(file_path.name, data)),
        ("imglink.io", lambda: _try_imglink(file_path.name, data)),
        ("file.io", lambda: _try_file_io(file_path.name, data)),
    ]:
        try:
            url = fn()
            if url:
                return _to_direct_image_url(url)
        except Exception:
            pass
    return None


def _try_tmpfiles(filename: str, data: bytes) -> str | None:
    """tmpfiles.org - 60min retention, no API key. Returns direct file URL."""
    r = requests.post(
        "https://tmpfiles.org/api/v1/upload",
        files={"file": (filename, data)},
        timeout=30,
    )
    if r.status_code == 200:
        j = r.json()
        url = (
            (j.get("data") or {}).get("url")
            or j.get("url")
            or j.get("link")
        )
        if url and str(url).startswith("http"):
            return str(url).strip()
    return None


def _try_0x0_st(filename: str, data: bytes) -> str | None:
    r = requests.post("https://0x0.st", files={"file": (filename, data)}, timeout=30)
    if r.status_code == 200:
        u = r.text.strip()
        if u.startswith("http"):
            return u
    return None


def _try_transfer_sh(filename: str, data: bytes) -> str | None:
    r = requests.put(
        f"https://transfer.sh/{filename}",
        data=data,
        headers={"Content-Type": "application/octet-stream"},
        timeout=30,
    )
    if r.status_code == 200:
        u = r.text.strip()
        if u.startswith("http"):
            return u
    return None


def _try_catbox(filename: str, data: bytes) -> str | None:
    r = requests.post(
        "https://litterbox.catbox.moe/resources/internals/api.php",
        data={"reqtype": "fileupload", "time": "24h"},
        files={"fileToUpload": (filename, data)},
        timeout=30,
    )
    if r.status_code == 200 and r.text.strip().startswith("https://"):
        return r.text.strip()
    return None


def _try_imglink(filename: str, data: bytes) -> str | None:
    r = requests.post(
        "https://imglink.io/upload",
        files={"image": (filename, data)},
        timeout=30,
    )
    if r.status_code == 200:
        j = r.json()
        url = j.get("url") or j.get("direct_link") or j.get("image", {}).get("url")
        if url and str(url).startswith("http"):
            return str(url)
    return None


def _try_file_io(filename: str, data: bytes) -> str | None:
    r = requests.post("https://file.io", files={"file": (filename, data)}, timeout=30)
    if r.status_code == 200:
        j = r.json()
        if j.get("success") and j.get("link"):
            return j["link"]
    return None


def _generate_scene_video_seedance(
    visual_description: str,
    scene_id: int,
    duration: int,
    start_image_path: Path,
    output_dir: Path,
) -> Path | None:
    """Pollinations Seedance Lite I2V. Returns Path or None on failure."""
    api_key = os.environ.get("POLLINATIONS_API_KEY")
    if not api_key:
        return None
    start_url = _upload_for_url(start_image_path)
    if not start_url:
        return None
    desc = visual_description[:MAX_PROMPT_CHARS].strip()
    full_prompt = f"Portrait cinematic video. {desc}. Smooth motion, Instagram Reel style."
    encoded_prompt = quote(full_prompt, safe="")
    clamped_duration = min(max(duration, 2), 10)
    base_url = f"https://gen.pollinations.ai/image/{encoded_prompt}"
    params = {
        "model": POLLINATIONS_SEEDANCE,
        "duration": clamped_duration,
        "aspectRatio": "9:16",
        "image": start_url,
    }
    try:
        r = requests.get(
            base_url,
            params=params,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=180,
        )
        if r.status_code == 200 and r.content:
            output_dir.mkdir(parents=True, exist_ok=True)
            out_path = output_dir / f"scene_{scene_id}.mp4"
            with open(out_path, "wb") as f:
                f.write(r.content)
            print(f"  [Scene {scene_id}] Pollinations Seedance (I2V) OK")
            return out_path
    except Exception:
        pass
    return None


def _generate_scene_video_grok(
    visual_description: str,
    scene_id: int,
    duration: int,
    output_dir: Path,
) -> Path | None:
    """
    Pollinations Grok T2V (text-to-video). No image needed.
    Returns Path or None on failure.
    """
    api_key = os.environ.get("POLLINATIONS_API_KEY")
    if not api_key:
        return None
    desc = visual_description[:MAX_PROMPT_CHARS].strip()
    full_prompt = f"Portrait cinematic video. {desc}. Smooth motion, Instagram Reel style, vertical 9:16."
    encoded_prompt = quote(full_prompt, safe="")
    clamped_duration = min(max(duration, 2), 10)
    base_url = f"https://gen.pollinations.ai/video/{encoded_prompt}"
    params = {
        "model": POLLINATIONS_GROK_VIDEO,
        "duration": clamped_duration,
        "aspectRatio": "9:16",
        "width": 576,
        "height": 1024,
    }
    try:
        r = requests.get(
            base_url,
            params=params,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=180,
        )
        if r.status_code == 200 and r.content and len(r.content) > 1000:
            output_dir.mkdir(parents=True, exist_ok=True)
            out_path = output_dir / f"scene_{scene_id}.mp4"
            with open(out_path, "wb") as f:
                f.write(r.content)
            print(f"  [Scene {scene_id}] Pollinations Grok (T2V) OK")
            return out_path
    except Exception:
        pass
    return None


def _fallback_image_to_clip(
    image_path: Path, scene_id: int, duration: int, output_dir: Path
) -> Path:
    """FFmpeg last resort: animate image with zoom when all AI video APIs fail."""
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"scene_{scene_id}.mp4"
    try:
        image_to_clip(image_path, float(duration), out_path, zoom=True)
    except RuntimeError:
        # x264 malloc failure on some systems; retry with lightweight mpeg4
        image_to_clip(image_path, float(duration), out_path, zoom=True, lightweight=True)
    return out_path


def generate_scene_video_from_images(
    visual_description: str,
    scene_id: int,
    duration: int,
    start_image_path: Path,
    end_image_path: Path,
    output_dir: Path = OUTPUT_DIR,
) -> Path:
    """
    Generate video clip: Seedance I2V -> Grok T2V -> FFmpeg fallback.
    """
    result = _generate_scene_video_seedance(
        visual_description, scene_id, duration, start_image_path, output_dir
    )
    if result:
        return result
    result = _generate_scene_video_grok(
        visual_description, scene_id, duration, output_dir
    )
    if result:
        return result
    print(f"  [Scene {scene_id}] Pollinations failed, using FFmpeg fallback")
    return _fallback_image_to_clip(start_image_path, scene_id, duration, output_dir)


def generate_all_scene_videos(
    scenes: list[dict],
    output_dir: Path = OUTPUT_DIR,
    start_end_pairs: list[tuple[Path, Path]] | None = None,
) -> list[Path]:
    """
    Generate one video clip per scene.
    Requires start_end_pairs (images). Uses Seedance Lite only; FFmpeg fallback.
    """
    paths = []
    use_images = start_end_pairs is not None and len(start_end_pairs) == len(scenes)

    if not use_images:
        raise ValueError(
            "Video generation requires images. Run Phase 2 with --video-gen to generate images."
        )

    for i, scene in enumerate(scenes):
        scene_id = scene.get("scene_id", i + 1)
        desc = scene.get("visual_description", "")
        duration = int(scene.get("duration", 5))
        if not desc:
            raise ValueError(f"Scene {scene_id} has no visual_description")

        start_path, end_path = start_end_pairs[i]
        path = generate_scene_video_from_images(
            desc, scene_id, duration, start_path, end_path, output_dir
        )
        paths.append(path)
    return paths
