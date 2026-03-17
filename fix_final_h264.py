"""Re-encode final.mp4 to H.264 540x960 for compatibility."""
import subprocess
import sys
from pathlib import Path

from imageio_ffmpeg import get_ffmpeg_exe


def fix_final(reel_dir: Path) -> None:
    inp = reel_dir / "final.mp4"
    tmp = reel_dir / "final_h264.mp4"
    if not inp.exists():
        print(f"Not found: {inp}")
        sys.exit(1)
    ff = get_ffmpeg_exe()
    # 360x640 = lowest memory for x264; 9:16 vertical
    cmd = [
        ff, "-y", "-i", str(inp),
        "-vf", "scale=360:640:force_original_aspect_ratio=decrease,pad=360:640:(ow-iw)/2:(oh-ih)/2",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-c:a", "aac", "-movflags", "+faststart",
        str(tmp),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        print("Error:", r.stderr[-1000:] if r.stderr else "")
        sys.exit(1)
    inp.unlink()
    tmp.rename(inp)
    print(f"Fixed: {inp}")


if __name__ == "__main__":
    dir_arg = sys.argv[1] if len(sys.argv) > 1 else "output/trust-reel"
    fix_final(Path(dir_arg))
