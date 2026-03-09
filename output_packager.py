"""
Oasis MVP 0.1 - Phase 5: Caption & Output Packaging
Writes caption.txt and hashtags.txt. No upload, no auth.
"""

from pathlib import Path


def write_caption(plan: dict, output_dir: Path) -> Path:
    """Write caption to caption.txt."""
    caption = plan.get("caption", "")
    path = output_dir / "caption.txt"
    path.write_text(caption, encoding="utf-8")
    return path


def write_hashtags(plan: dict, output_dir: Path) -> Path:
    """Write hashtags to hashtags.txt (space-separated)."""
    hashtags = plan.get("hashtags", [])
    text = " ".join(hashtags) if isinstance(hashtags, list) else str(hashtags)
    path = output_dir / "hashtags.txt"
    path.write_text(text, encoding="utf-8")
    return path


def package_output(
    plan: dict,
    mp4_path: Path,
    output_dir: Path,
) -> dict[str, Path]:
    """
    Write final outputs: MP4 (already exists), caption.txt, hashtags.txt.

    Returns:
        Dict mapping 'mp4', 'caption', 'hashtags' to their paths
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    caption_path = write_caption(plan, output_dir)
    hashtags_path = write_hashtags(plan, output_dir)
    return {
        "mp4": mp4_path,
        "caption": caption_path,
        "hashtags": hashtags_path,
    }
