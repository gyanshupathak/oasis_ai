"""
Oasis MVP 0.2 - Video Assembly Engine
Cinematic pipeline: images/video assembly, word-by-word subtitles.
"""

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from config import (
    CROSSFADE_DURATION,
    IMAGE_HEIGHT,
    IMAGE_WIDTH,
    MUSIC_DIR,
    MUSIC_VOLUME,
    OUTPUT_DIR,
    OUTPUT_HEIGHT,
    OUTPUT_WIDTH,
)
from voiceover import (
    build_voiceover_subtitle_events,
    get_subtitle_events_from_audio,
    word_events_to_batched_display,
)

# Locked design decisions
FONT = "Arial"  # Fallback: Arial on Windows. Use "DejaVu-Sans" on Linux.
FONT_SIZE = 48
TEXT_COLOR = "white"
TEXT_BORDER = "black"
ZOOM_FACTOR = 1.1  # Slow zoom in over clip duration
FADE_DURATION = 0.5  # seconds


def _get_ffmpeg_exe() -> str:
    """Get ffmpeg executable path. Uses imageio-ffmpeg bundle if system ffmpeg not found."""
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        return get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def _get_media_duration(path: Path) -> float:
    """Get duration in seconds. Use wave for WAV, ffmpeg stderr for video."""
    path = Path(path)
    if path.suffix.lower() == ".wav":
        import wave
        with wave.open(str(path), "rb") as wf:
            return wf.getnframes() / wf.getframerate()
    # ffmpeg -i prints "Duration: HH:MM:SS.xx" to stderr
    exe = _get_ffmpeg_exe()
    result = subprocess.run(
        [exe, "-i", str(path.resolve())],
        capture_output=True, text=True,
    )
    import re
    match = re.search(r"Duration: (\d+):(\d+):(\d+)\.(\d+)", result.stderr)
    if not match:
        raise RuntimeError(f"Could not parse duration from: {result.stderr[:500]}")
    h, m, s, cs = (int(match.group(i)) for i in range(1, 5))
    return h * 3600 + m * 60 + s + cs / 100


def _run_ffmpeg(args: list[str]) -> None:
    """Run FFmpeg, raise on failure."""
    exe = _get_ffmpeg_exe()
    cmd = [exe, "-y", "-hide_banner", "-loglevel", "error"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed: {result.stderr}")


def image_to_clip(
    image_path: Path,
    duration: float,
    output_path: Path,
    zoom: bool = True,
    width: int = 1024,
    height: int = 1792,
    lightweight: bool = False,
) -> None:
    """
    Convert single image to video clip with slow zoom and fade in/out.

    Args:
        image_path: Input image (PNG/JPG)
        duration: Clip duration in seconds
        output_path: Output video path
        zoom: Apply slow zoom effect
        width: Output width (default 1024)
        height: Output height (default 1792)
        lightweight: Use mpeg4 + smaller size to avoid x264 malloc issues
    """
    if lightweight:
        width, height = 540, 960  # Half res for low-memory systems
    size = f"{width}x{height}"
    # FFmpeg: loop image → zoompan (slow zoom in) → fade in/out
    # zoompan z: zoom per frame. d=1, fps=30, s=output size
    if zoom:
        zoom_expr = f"min(zoom+0.0008,{ZOOM_FACTOR})"
        vf = (
            f"zoompan=z='{zoom_expr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={size}:fps=30,"
            f"fade=t=in:st=0:d={FADE_DURATION},"
            f"fade=t=out:st={max(0,duration - FADE_DURATION)}:d={FADE_DURATION}"
        )
    else:
        vf = (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
            f"fade=t=in:st=0:d={FADE_DURATION},"
            f"fade=t=out:st={max(0,duration - FADE_DURATION)}:d={FADE_DURATION}"
        )

    args = [
        "-loop", "1",
        "-i", str(image_path.resolve()),
        "-t", str(duration),
        "-vf", vf,
        "-pix_fmt", "yuv420p",
    ]
    if lightweight:
        args.extend(["-c:v", "mpeg4", "-q:v", "5"])
    args.append(str(output_path.resolve()))
    _run_ffmpeg(args)


# Position mapping for drawtext (9:16 vertical)
_POSITION_EXPR = {
    "bottom-center": "x=(w-text_w)/2:y=h-120",
    "top-center": "x=(w-text_w)/2:y=80",
    "center": "x=(w-text_w)/2:y=(h-text_h)/2",
    "top-left": "x=80:y=80",
    "top-right": "x=w-text_w-80:y=80",
    "bottom-left": "x=80:y=h-120",
    "bottom-right": "x=w-text_w-80:y=h-120",
}


def add_text_overlay(
    video_path: Path,
    text: str,
    output_path: Path,
) -> None:
    """
    Overlay text on video. Center-bottom, one line. Escape special chars for FFmpeg.
    """
    if not text:
        shutil.copy2(video_path, output_path)
        return

    # Escape drawtext special chars: \ ' : 
    escaped = text.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:")
    # drawtext: fontfile, text, x=(w-tw)/2, y=h-100 (bottom center)
    drawtext = (
        f"drawtext=text='{escaped}':fontsize={FONT_SIZE}:fontcolor={TEXT_COLOR}:"
        f"borderw=2:bordercolor={TEXT_BORDER}:x=(w-text_w)/2:y=h-120"
    )

    _run_ffmpeg([
        "-i", str(video_path),
        "-vf", drawtext,
        "-c:a", "copy",
        str(output_path),
    ])


def add_text_overlay_with_config(
    video_path: Path,
    overlay_config: dict,
    duration: float,
    output_path: Path,
) -> None:
    """
    Overlay text with AI-decided position, timing, and fade effect.
    overlay_config: { show, content, position, start_time, end_time, effect }
    """
    text_cfg = overlay_config.get("text", {}) if isinstance(overlay_config, dict) else {}
    if not text_cfg.get("show") or not text_cfg.get("content"):
        shutil.copy2(video_path, output_path)
        return

    content = str(text_cfg.get("content", "")).strip()
    if not content:
        shutil.copy2(video_path, output_path)
        return

    escaped = content.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:")
    start = max(0, float(text_cfg.get("start_time", 0.5)))
    end = min(duration, float(text_cfg.get("end_time", duration - 0.5)))
    if end <= start:
        end = start + 1

    pos = text_cfg.get("position", "bottom-center")
    pos_expr = _POSITION_EXPR.get(pos, _POSITION_EXPR["bottom-center"])

    # enable: only draw between start and end (escape commas for FFmpeg filter syntax)
    enable = f"between(t\\,{start}\\,{end})"

    # Text styling (effect "fade"/"slide" use same enable-based timing; alpha fade would need blend filter)
    drawtext = (
        f"drawtext=text='{escaped}':fontsize={FONT_SIZE}:fontcolor=white:"
        f"borderw=2:bordercolor=black:{pos_expr}:"
        f"enable='{enable}'"
    )

    _run_ffmpeg([
        "-i", str(video_path),
        "-vf", drawtext,
        "-c:a", "copy",
        str(output_path),
    ])


def concat_clips(clip_paths: list[Path], output_path: Path) -> None:
    """Concatenate video clips. Pre-scale each to same format then concat (avoids x264 malloc on long reels)."""
    if len(clip_paths) > 1:
        _concat_clips_prescale_then_concat(clip_paths, output_path)
        return
    _concat_clips_hard_cut(clip_paths, output_path)


def _concat_clips_prescale_then_concat(clip_paths: list[Path], output_path: Path) -> None:
    """
    Scale each clip to OUTPUT_WxH, H.264 (one at a time = low memory), then concat with copy.
    No crossfade but avoids x264 malloc on long reels; produces compatible H.264 output.
    """
    import tempfile
    with tempfile.TemporaryDirectory(prefix="oasis_concat_") as work_dir:
        work_dir = Path(work_dir)
        scaled = []
        scale_vf = f"scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:force_original_aspect_ratio=decrease,pad={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:(ow-iw)/2:(oh-ih)/2,fps=30"
        for i, p in enumerate(clip_paths):
            sp = work_dir / f"scaled_{i}.mp4"
            _run_ffmpeg([
                "-i", str(p),
                "-vf", scale_vf,
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                "-an", "-movflags", "+faststart",
                str(sp),
            ])
            scaled.append(sp)
        if len(scaled) == 1:
            shutil.copy2(scaled[0], output_path)
        else:
            list_file = work_dir / "list.txt"
            with open(list_file, "w", encoding="utf-8") as f:
                for s in scaled:
                    pstr = str(s.resolve()).replace("\\", "/")
                    f.write(f"file '{pstr}'\n")
            _run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(output_path)])


def _concat_clips_hard_cut(clip_paths: list[Path], output_path: Path) -> None:
    """Concatenate with hard cuts (single clip)."""
    list_file = output_path.with_suffix(".concat_list.txt")
    with open(list_file, "w", encoding="utf-8") as f:
        for p in clip_paths:
            path_str = str(p.resolve()).replace("\\", "/")
            f.write(f"file '{path_str}'\n")
    _run_ffmpeg([
        "-f", "concat", "-safe", "0",
        "-i", str(list_file.resolve()),
        "-c", "copy",
        str(output_path.resolve()),
    ])
    list_file.unlink(missing_ok=True)


def _concat_clips_with_crossfade(clip_paths: list[Path], output_path: Path) -> None:
    """Concatenate clips with crossfade. Output H.264 at OUTPUT_WIDTH x OUTPUT_HEIGHT for max compatibility."""
    fade = CROSSFADE_DURATION
    durations = [_get_media_duration(p) for p in clip_paths]
    n = len(clip_paths)
    if n < 2:
        _concat_clips_hard_cut(clip_paths, output_path)
        return

    # Scale to output res; fps=30 normalizes timebase for xfade
    scale_pad = f"scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:force_original_aspect_ratio=decrease,pad={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:(ow-iw)/2:(oh-ih)/2,fps=30"
    inputs = ["-i", str(clip_paths[0].resolve())]
    for p in clip_paths[1:]:
        inputs.extend(["-i", str(p.resolve())])

    scaled_labels = [f"v{i}" for i in range(n)]
    scale_filters = [f"[{i}:v]{scale_pad}[{scaled_labels[i]}]" for i in range(n)]

    prev_label = scaled_labels[0]
    running_dur = durations[0]
    xfade_filters = []
    for i in range(1, n):
        offset = max(0, running_dur - fade)
        in_label = scaled_labels[i]
        out_label = f"xf{i}" if i < n - 1 else "outv"
        xfade_filters.append(f"[{prev_label}][{in_label}]xfade=transition=fade:duration={fade}:offset={offset:.3f}[{out_label}]")
        running_dur = running_dur + durations[i] - fade
        prev_label = out_label

    filter_complex = ";".join(scale_filters) + ";" + ";".join(xfade_filters)
    # Try H.264 first; fallback to mpeg4 if malloc (some systems)
    args = inputs + ["-filter_complex", filter_complex, "-map", "[outv]", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-threads", "2", "-an", "-movflags", "+faststart", str(output_path.resolve())]
    try:
        _run_ffmpeg(args)
    except RuntimeError as e:
        if "malloc" in str(e).lower() or "x264" in str(e).lower():
            args_mpeg4 = inputs + ["-filter_complex", filter_complex, "-map", "[outv]", "-c:v", "mpeg4", "-q:v", "5", "-an", str(output_path.resolve())]
            _run_ffmpeg(args_mpeg4)
        else:
            raise


def _seconds_to_ass_time(sec: float) -> str:
    """Convert seconds to ASS time format H:MM:SS.cc"""
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    cs = int((sec % 1) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


# Subtitle styling: larger font + strong outline (presets override these)
SUBTITLE_FONT_SIZE = 76
SUBTITLE_OUTLINE = 5
SUBTITLE_MARGIN_V = 80
# Word-by-word: max words on screen at once (3-4).
SUBTITLE_MAX_WORDS_ON_SCREEN = 4
# ASS Alignment: 2=bottom-center, 5=middle-center (numpad), 8=top-center
# Use explicit \pos(512,896) for reliable center (PlayRes 1024x1792)
SUBTITLE_ALIGNMENT = 5


def _escape_ass_char(c: str) -> str:
    """Escape single char for ASS (only backslash and braces in text content)."""
    if c in ("\\", "{", "}"):
        return "\\" + c
    return c


def _text_to_karaoke_ass(text: str, duration_sec: float) -> str:
    """
    Convert text to ASS karaoke format for letter-by-letter reveal.
    Each character gets equal display time via ASS karaoke tags (centiseconds).
    """
    chars = list(text)
    if not chars:
        return ""
    cs_per_char = max(2, int((duration_sec * 100) / len(chars)))
    parts = []
    for c in chars:
        escaped = _escape_ass_char(c)
        parts.append(f"{{\\kf{cs_per_char}}}{escaped}")
    return "".join(parts)


def _hex_to_ass_bgr(hex_str: str) -> str:
    """Convert #RRGGBB to ASS &HAABBGGRR (alpha BB GG RR)."""
    hex_str = hex_str.lstrip("#")
    r, g, b = int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)
    return f"&H00{b:02X}{g:02X}{r:02X}"


def _format_text_keyword_highlight(text: str, keyword_color_hex: str, num_words: int = 3) -> str:
    """Wrap first num_words in ASS color override. Returns ASS-escaped text."""
    words = text.split()
    if not keyword_color_hex:
        return "".join(_escape_ass_char(c) for c in text)
    color = _hex_to_ass_bgr(keyword_color_hex)
    if len(words) <= num_words:
        head_esc = "".join(_escape_ass_char(c) for c in text)
        return f"{{\\c{color}}}{head_esc}"
    head = " ".join(words[:num_words])
    tail = " " + " ".join(words[num_words:])
    head_esc = "".join(_escape_ass_char(c) for c in head)
    tail_esc = "".join(_escape_ass_char(c) for c in tail)
    return f"{{\\c{color}}}{head_esc}{{\\r}}{tail_esc}"


def _write_ass_file(events: list[dict], path: Path, letter_by_letter: bool = True) -> None:
    """Write ASS subtitle file. Word-by-word: one word per event."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "[Script Info]",
        "Title: Oasis On-Screen Text",
        "ScriptType: v4.00+",
        "WrapStyle: 0",
        "PlayResX: 1024",
        "PlayResY: 1792",
        "LayoutResX: 1024",
        "LayoutResY: 1792",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,Arial,{SUBTITLE_FONT_SIZE},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,{SUBTITLE_OUTLINE},2,{SUBTITLE_ALIGNMENT},30,30,0,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for ev in events:
        start_s = _seconds_to_ass_time(ev["start"])
        end_s = _seconds_to_ass_time(ev["end"])
        raw_text = ev["text"]
        text = "".join(_escape_ass_char(c) for c in raw_text)
        # Explicit center: \pos(512,896) = center of 1024x1792, \an5 = anchor at center
        lines.append(f"Dialogue: 0,{start_s},{end_s},Default,,0,0,0,,{{\\pos(512,896)\\an5}}{text}")
    path.write_text("\n".join(lines), encoding="utf-8")


def burn_in_voiceover_subtitles(
    video_path: Path,
    scene_plan: dict,
    output_path: Path,
    voiceover_path: Path | None = None,
    time_scale: float = 1.0,
) -> None:
    """
    Burn voiceover subtitles into video. Word-by-word, max 3-4 words on screen, centered.
    Uses faster-whisper for accurate timing when voiceover exists.
    time_scale: multiply event times (e.g. 30/33 when voiceover was sped to 30s from 33s).
    """
    events = []
    actual_audio_dur = None
    if voiceover_path and voiceover_path.exists():
        try:
            actual_audio_dur = _get_media_duration(voiceover_path)
        except Exception:
            pass
        # Word-by-word from Whisper: batch of 4 — word 1, 1+2, 1+2+3, 1+2+3+4, then all clear
        word_events = get_subtitle_events_from_audio(voiceover_path, phrase_level=False)
        if word_events:
            events = word_events_to_batched_display(
                word_events, max_words=SUBTITLE_MAX_WORDS_ON_SCREEN
            )
        if events and actual_audio_dur and actual_audio_dur > 0.1:
            last_end = max(ev["end"] for ev in events)
            if last_end < actual_audio_dur * 0.85:
                scale = actual_audio_dur / last_end
                for ev in events:
                    ev["start"] *= scale
                    ev["end"] *= scale
    if not events:
        word_events = build_voiceover_subtitle_events(
            scene_plan, actual_audio_duration=actual_audio_dur, word_level=True
        )
        events = word_events_to_batched_display(
            word_events, max_words=SUBTITLE_MAX_WORDS_ON_SCREEN
        )
    if time_scale != 1.0 and events:
        for ev in events:
            ev["start"] *= time_scale
            ev["end"] *= time_scale
    if not events:
        shutil.copy2(video_path, output_path)
        return

    ass_dir = output_path.parent
    ass_dir.mkdir(parents=True, exist_ok=True)
    ass_path = ass_dir / "voiceover.ass"
    _write_ass_file(events, ass_path, letter_by_letter=False)

    font_size = SUBTITLE_FONT_SIZE
    outline = SUBTITLE_OUTLINE
    margin_v = SUBTITLE_MARGIN_V

    ass_str = str(ass_path.resolve()).replace("\\", "/")
    if len(ass_str) > 1 and ass_str[1] == ":":
        ass_str = ass_str[0] + "\\:" + ass_str[2:]
    # Middle-center: \an5 in each Dialogue; force_style as backup
    vf = f"subtitles='{ass_str}':force_style='Alignment=5,MarginV=0,FontSize={font_size},Outline={outline}'"
    # Scale to output res + burn subtitles; H.264 for compatibility
    scale_first = f"scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:force_original_aspect_ratio=decrease,pad={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:(ow-iw)/2:(oh-ih)/2"
    full_vf = f"{scale_first},{vf}"
    _run_ffmpeg([
        "-i", str(video_path),
        "-vf", full_vf,
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-c:a", "copy",
        "-movflags", "+faststart",
        str(output_path),
    ])


def _normalize_voiceover_to_duration(
    voiceover_path: Path,
    target_sec: float,
    output_path: Path,
) -> Path:
    """
    Speed up or slow down voiceover to exactly target_sec.
    Uses FFmpeg atempo. Returns path to normalized audio.
    """
    actual = _get_media_duration(voiceover_path)
    if actual <= 0.1:
        shutil.copy2(voiceover_path, output_path)
        return output_path
    factor = actual / target_sec
    if 0.99 <= factor <= 1.01:
        shutil.copy2(voiceover_path, output_path)
        return output_path
    exe = _get_ffmpeg_exe()
    args = [
        "-i", str(voiceover_path),
        "-filter:a", f"atempo={factor}",
        "-y", str(output_path),
    ]
    result = subprocess.run([exe, "-hide_banner", "-loglevel", "error"] + args, capture_output=True, text=True)
    if result.returncode != 0:
        shutil.copy2(voiceover_path, output_path)
        return output_path
    return output_path


def _mix_voiceover_with_music(
    voiceover_path: Path,
    music_path: Path,
    output_path: Path,
    music_volume: float = MUSIC_VOLUME,
) -> Path:
    """Mix voiceover (full volume) with music (low volume). Output length = voiceover length."""
    vo_dur = _get_media_duration(voiceover_path)
    # amix duration=first: mix until first input ends. Music loops or trims automatically.
    filter_complex = (
        f"[0:a]volume=1[vo];"
        f"[1:a]volume={music_volume},atrim=0:{vo_dur},asetpts=PTS-STARTPTS[mus];"
        f"[vo][mus]amix=inputs=2:duration=first:dropout_transition=0[a]"
    )
    _run_ffmpeg([
        "-i", str(voiceover_path),
        "-i", str(music_path),
        "-filter_complex", filter_complex,
        "-map", "[a]", "-c:a", "aac",
        "-t", str(vo_dur),
        str(output_path),
    ])
    return output_path


def mux_audio_video(video_path: Path, audio_path: Path, output_path: Path) -> None:
    """
    Mux video with our voiceover. Stretch/compress video to match voiceover duration
    so both end at the same time (voiceover is source of truth).
    """
    video_dur = _get_media_duration(video_path)
    audio_dur = _get_media_duration(audio_path)

    args = ["-i", str(video_path), "-i", str(audio_path)]
    # Match video length to voiceover when they differ by more than 0.5s
    if abs(video_dur - audio_dur) > 0.5:
        factor = audio_dur / video_dur
        args.extend(["-vf", f"setpts=PTS*{factor}", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-movflags", "+faststart"])
    else:
        args.extend(["-c:v", "copy"])
    args.extend([
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:a", "aac",
        "-t", str(audio_dur),
        str(output_path),
    ])
    _run_ffmpeg(args)


def trim_to_duration(video_path: Path, duration_sec: float, output_path: Path) -> None:
    """Trim video (and muxed audio) to exact duration."""
    _run_ffmpeg([
        "-i", str(video_path),
        "-t", str(duration_sec),
        "-c", "copy",
        str(output_path),
    ])


def assemble_reel_from_videos(
    scene_plan: dict,
    video_dir: Path,
    voiceover_path: Path | None,
    output_path: Path,
    max_duration_sec: float | None = None,
) -> Path:
    """
    Assemble final reel from pre-generated video clips.
    Concat clips + mux voiceover. No FFmpeg image processing.
    max_duration_sec: trim output to this length (e.g. 60 for strict 60s reel).
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    work_dir = Path(tempfile.mkdtemp(prefix="oasis_"))

    clip_paths = []
    for i, scene in enumerate(scene_plan["scenes"]):
        scene_id = scene.get("scene_id", i + 1)
        clip_path = video_dir / f"scene_{scene_id}.mp4"
        if not clip_path.exists():
            clip_path = video_dir / f"scene_{i + 1}.mp4"
        if not clip_path.exists():
            raise FileNotFoundError(f"Missing video: {clip_path}")
        clip_paths.append(clip_path)

    concat_path = work_dir / "concat.mp4"
    concat_clips(clip_paths, concat_path)

    time_scale = 1.0
    if voiceover_path and voiceover_path.exists():
        audio_to_use = voiceover_path
        if max_duration_sec and max_duration_sec > 0:
            actual_dur = _get_media_duration(voiceover_path)
            if actual_dur > max_duration_sec:
                normalized = work_dir / "voiceover_norm.wav"
                _normalize_voiceover_to_duration(voiceover_path, float(max_duration_sec), normalized)
                audio_to_use = normalized
                time_scale = float(max_duration_sec) / actual_dur
        # Optional: mix in subtle background music (local file only)
        music_mood = (scene_plan.get("music_mood") or "ambient").lower().strip()
        music_path = None
        for mood_candidate in [music_mood, "inspiring", "ambient"]:
            for name in [f"{mood_candidate}.mp3", f"{mood_candidate}.mp3.mp3"]:
                local_path = MUSIC_DIR / name
                if local_path.exists():
                    music_path = local_path
                    break
            if music_path:
                break
        if music_path:
            mixed_path = work_dir / "voiceover_with_music.m4a"
            _mix_voiceover_with_music(audio_to_use, music_path, mixed_path)
            audio_to_use = mixed_path
        muxed_path = work_dir / "muxed.mp4"
        mux_audio_video(concat_path, audio_to_use, muxed_path)
        with_subs = work_dir / "with_subs.mp4"
        burn_in_voiceover_subtitles(muxed_path, scene_plan, with_subs, voiceover_path, time_scale=time_scale)
        if max_duration_sec and max_duration_sec > 0:
            trim_to_duration(with_subs, max_duration_sec, output_path)
        else:
            shutil.copy2(with_subs, output_path)
    else:
        burn_in_voiceover_subtitles(concat_path, scene_plan, output_path)
        if max_duration_sec and max_duration_sec > 0:
            trimmed = work_dir / "trimmed.mp4"
            trim_to_duration(output_path, max_duration_sec, trimmed)
            shutil.move(trimmed, output_path)

    try:
        for f in work_dir.iterdir():
            if f.is_file():
                f.unlink()
            else:
                shutil.rmtree(f)
        work_dir.rmdir()
    except Exception:
        shutil.rmtree(work_dir, ignore_errors=True)
    return output_path


def assemble_reel(
    scene_plan: dict,
    image_dir: Path,
    voiceover_path: Path | None,
    output_path: Path,
) -> Path:
    """
    Full pipeline: images + plan → final MP4 (FFmpeg zoompan + voiceover subtitles).
    Voiceover text appears on screen phrase-by-phrase, synced with speech, no gaps.
    Use assemble_reel_from_videos when you have pre-generated video clips.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    work_dir = output_path.parent / "_work"
    work_dir.mkdir(exist_ok=True)

    clips_raw = []

    for i, scene in enumerate(scene_plan["scenes"]):
        scene_id = scene.get("scene_id", i + 1)
        duration = float(scene.get("duration", 4))

        img_path = image_dir / f"scene_{scene_id}.png"
        if not img_path.exists():
            img_path = image_dir / f"scene_{i + 1}.png"
        if not img_path.exists():
            raise FileNotFoundError(f"Missing image: {img_path}")

        raw_clip = work_dir / f"scene_{scene_id}_raw.mp4"
        image_to_clip(img_path, duration, raw_clip)
        clips_raw.append(raw_clip)

    # Concat all (no per-clip text; we add full voiceover subtitles at the end)
    concat_path = work_dir / "concat.mp4"
    concat_clips(clips_raw, concat_path)

    if voiceover_path and voiceover_path.exists():
        muxed_path = work_dir / "muxed.mp4"
        mux_audio_video(concat_path, voiceover_path, muxed_path)
        burn_in_voiceover_subtitles(muxed_path, scene_plan, output_path, voiceover_path)
    else:
        burn_in_voiceover_subtitles(concat_path, scene_plan, output_path)

    # Cleanup work dir
    for f in work_dir.iterdir():
        f.unlink()
    work_dir.rmdir()

    return output_path
