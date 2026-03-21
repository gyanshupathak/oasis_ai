"""
Assemble reel and ensure H.264 output for compatibility.
Usage (from repo root): python scripts/assemble_and_fix.py output/trust-reel 60
"""
import subprocess
import sys
from pathlib import Path

from imageio_ffmpeg import get_ffmpeg_exe

ROOT = Path(__file__).resolve().parent.parent


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/assemble_and_fix.py <output_folder> [length]")
        print("Example: python scripts/assemble_and_fix.py output/trust-reel 60")
        sys.exit(1)
    folder = Path(sys.argv[1])
    folder = folder.resolve() if folder.is_absolute() else (ROOT / folder).resolve()
    length = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    plan = folder / "scene_plan.json"
    if not plan.exists():
        print(f"Not found: {plan}")
        sys.exit(1)

    slug = folder.name
    cmd = [
        sys.executable,
        str(ROOT / "main.py"),
        "--plan",
        str(plan),
        "--assemble-only",
        "--name",
        slug,
        "--length",
        str(length),
    ]
    print("Step 1: Assembling...")
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode != 0:
        sys.exit(r.returncode)

    final = folder / "final.mp4"
    if not final.exists():
        print("Assembly did not produce final.mp4")
        sys.exit(1)

    print("Step 2: Converting to H.264...")
    ff = get_ffmpeg_exe()
    tmp = folder / "final_h264.mp4"
    fix_cmd = [
        ff,
        "-y",
        "-i",
        str(final),
        "-vf",
        "scale=360:640:force_original_aspect_ratio=decrease,pad=360:640:(ow-iw)/2:(oh-ih)/2",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        str(tmp),
    ]
    r2 = subprocess.run(fix_cmd, capture_output=True, text=True, timeout=600)
    if r2.returncode == 0:
        final.unlink()
        tmp.rename(final)
        print(f"Done: {final} (H.264 360x640)")
    else:
        print("H.264 conversion failed; keeping original. Try playing in VLC.")
        if tmp.exists():
            tmp.unlink()
        print(r2.stderr[-500:] if r2.stderr else "")


if __name__ == "__main__":
    main()
