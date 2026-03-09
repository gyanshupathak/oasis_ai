"""
Oasis MVP 0.1 - Main Entry Point
Convert LinkedIn/Twitter posts -> Instagram Reels.
Pipeline: Phase 1 (Scene Plan + Overlays) -> Images -> Voiceover -> Video Gen -> Assemble -> Caption
Each run saves to a separate folder under output/ (e.g. output/2026-recap-post/).
"""

import argparse
import re
from pathlib import Path

from config import DEFAULT_REEL_LENGTH, OUTPUT_DIR


def _slugify(name: str, max_len: int = 40) -> str:
    """Turn '2026 recap post' -> '2026-recap-post'."""
    s = re.sub(r"[^\w\s-]", "", name.lower())
    s = re.sub(r"[-\s]+", "-", s).strip("-")
    return s[:max_len] if max_len else s


def _get_or_generate_start_end_pairs(
    plan: dict, output_dir: Path, phase: int | None, frames_per_scene: int = 4
) -> list[tuple[Path, Path]]:
    """
    Use existing scene_N.png for I2V when all exist; else generate via Phase 2.
    Wan 2.6 uses a single start frame, so we pass (path, path) per scene.
    """
    scenes = plan.get("scenes", [])
    existing = []
    for i, scene in enumerate(scenes):
        scene_id = scene.get("scene_id", i + 1)
        p = output_dir / f"scene_{scene_id}.png"
        if not p.exists():
            p = output_dir / f"scene_{i + 1}.png"
        if p.exists():
            existing.append((Path(p), Path(p)))
        else:
            break
    if len(existing) == len(scenes):
        print("[Phase 2] Using existing images for I2V (scene_*.png)")
        return existing
    return run_phase2(plan, output_dir, for_video_gen=True, frames_per_scene=frames_per_scene)


from image_generator import (
    generate_all_scene_images,
    generate_four_frames_per_scene,
    generate_single_frames,
)
from output_packager import package_output
from overlay_planner import plan_overlays
from scene_planner import generate_scenes, load_scene_plan, save_scene_plan
from video_assembler import assemble_reel, assemble_reel_from_videos
from video_generator import generate_all_scene_videos
from voiceover import build_voiceover_from_plan, generate_voiceover


def run_phase1(
    text: str,
    reel_length: int,
    voiceover: bool,
    output_dir: Path,
    num_scenes: int | None = None,
    duration_per_scene: int | None = None,
) -> tuple[dict, Path]:
    """Phase 1: Generate scene plan + AI overlay planner (Phase 1.5)."""
    print("[Phase 1] Scene Planning...")
    plan = generate_scenes(
        text,
        reel_length=reel_length,
        voiceover_on=voiceover,
        num_scenes=num_scenes,
        duration_per_scene=duration_per_scene,
    )
    print(f"  -> {len(plan['scenes'])} scenes, {plan['total_duration']}s total")

    print("[Phase 1.5] AI Overlay Planner...")
    plan = plan_overlays(plan)
    print(f"  -> Overlay decisions added for each scene")

    plan_path = output_dir / "scene_plan.json"
    save_scene_plan(plan, plan_path)
    print(f"  -> Saved: {plan_path}")
    return plan, plan_path


def run_phase2(
    plan: dict, output_dir: Path, for_video_gen: bool = False, frames_per_scene: int = 4
) -> list[Path] | list[tuple[Path, Path]]:
    """
    Phase 2: Generate images.
    If for_video_gen: 1 or 4 keyframes per scene for I2V (Wan/minimax use first frame).
    Else: one image per scene for FFmpeg assembly.
    """
    if for_video_gen:
        if frames_per_scene == 4:
            print("[Phase 2] 4 Keyframes per scene (for I2V)...")
            pairs = generate_four_frames_per_scene(plan["scenes"], output_dir)
        else:
            print("[Phase 2] 1 Frame per scene (for I2V)...")
            pairs = generate_single_frames(plan["scenes"], output_dir)
        print(f"  -> {len(pairs)} scenes x {frames_per_scene} image(s)")
        return pairs
    print("[Phase 2] Image Generation...")
    paths = generate_all_scene_images(plan["scenes"], output_dir)
    print(f"  -> {len(paths)} images saved")
    return paths

def run_phase3(plan: dict, voiceover_on: bool, output_dir: Path) -> Path | None:
    """Phase 3: Generate voiceover audio."""
    if not voiceover_on:
        print("[Phase 3] Voiceover skipped (--no-voiceover)")
        return None
    print("[Phase 3] Voiceover...")
    full_text, _ = build_voiceover_from_plan(plan, voiceover_on=True)
    if not full_text.strip():
        print("  -> No voiceover text, skipped")
        return None
    path = generate_voiceover(full_text, output_path=output_dir / "voiceover.wav")
    print(f"  -> Saved: {path}")
    return path

def run_phase4_video(
    plan: dict, output_dir: Path, start_end_pairs: list[tuple[Path, Path]] | None = None
) -> list[Path]:
    """Phase 4: Generate video clips (Wan 2.6 image-to-video from start frames)."""
    print("[Phase 4] Video Generation (Seedance Lite)...")
    paths = generate_all_scene_videos(plan["scenes"], output_dir, start_end_pairs=start_end_pairs)
    print(f"  -> {len(paths)} video clips saved")
    return paths

def run_phase5_assemble(
    plan: dict,
    output_dir: Path,
    voiceover_path: Path | None,
    use_videos: bool,
    max_duration_sec: int | None = None,
    output_path: Path | None = None,
) -> Path:
    """Phase 5: Assemble final reel (concat + mux voiceover)."""
    print("[Phase 5] Video Assembly...")
    mp4_path = output_path or (output_dir / "final.mp4")
    if use_videos:
        assemble_reel_from_videos(
            plan, output_dir, voiceover_path, mp4_path,
            max_duration_sec=max_duration_sec,
        )
    else:
        assemble_reel(plan, output_dir, voiceover_path, mp4_path)
    print(f"  -> Saved: {mp4_path}")
    return mp4_path

def run_phase6_package(plan: dict, mp4_path: Path, output_dir: Path) -> dict[str, Path]:
    """Phase 6: Write caption and hashtags (optional)."""
    print("[Phase 6] Packaging...")
    out = package_output(plan, mp4_path, output_dir)
    print(f"  -> caption.txt, hashtags.txt")
    return out

def main():
    parser = argparse.ArgumentParser(description="Oasis: LinkedIn/Twitter -> Instagram Reels")
    parser.add_argument("--text", "-t", type=str, help="Post text (or path to .txt file)")
    parser.add_argument("--length", "-l", type=int, default=DEFAULT_REEL_LENGTH, help="Reel length in seconds")
    parser.add_argument("--scenes", "-s", type=int, help="Number of scenes (e.g. 20). With --length 60, duration per scene = 3s")
    parser.add_argument("--no-voiceover", action="store_true", help="Skip Gemini TTS voiceover")
    parser.add_argument("--output", "-o", type=Path, default=OUTPUT_DIR, help="Output directory")
    parser.add_argument(
        "--phase", "-p", type=int, choices=[1, 2, 3, 4, 5, 6],
        help="Run only up to this phase",
    )
    parser.add_argument("--plan", type=Path, help="Use existing scene_plan.json (skip Phase 1)")
    parser.add_argument(
        "--video-gen",
        action="store_true",
        default=True,
        help="Use Pollinations video gen (Phase 4) - cinematic AI visuals",
    )
    parser.add_argument(
        "--no-caption",
        action="store_true",
        help="Skip caption and hashtags (Phase 6)",
    )
    parser.add_argument(
        "--name", "-n", type=str,
        help="Folder name for this run (e.g. '2026 recap post' -> output/2026-recap-post/)",
    )
    parser.add_argument(
        "--frames", "-f", type=int, choices=[1, 4], default=1,
        help="Keyframes per scene for I2V: 1 or 4. I2V uses first frame.",
    )
    parser.add_argument(
        "--assemble-only",
        action="store_true",
        help="Re-run only Phase 5 (assembly). Use with --plan. Does not regenerate images, voiceover, or video clips.",
    )
    args = parser.parse_args()

    text = args.text
    if not args.plan and not text:
        parser.error("--text or --plan is required")
    if args.assemble_only and not args.plan:
        parser.error("--assemble-only requires --plan (path to scene_plan.json)")
    if args.plan and not args.plan.exists():
        parser.error(f"Plan file not found: {args.plan}")
    if text and Path(text).exists():
        text = Path(text).read_text(encoding="utf-8")

    base_output = args.output
    final_output_dir: Path | None = None
    if args.plan:
        output_dir = args.plan.parent
        if args.name:
            final_output_dir = base_output / _slugify(args.name)
            final_output_dir.mkdir(parents=True, exist_ok=True)
            print(f"[Output] Source: {output_dir} -> Final: {final_output_dir}")
        else:
            print(f"[Output] Using folder: {output_dir}")
    else:
        folder_name = args.name
        if not folder_name and text:
            folder_name = text.strip().split("\n")[0].strip()[:50] or "reel"
        slug = _slugify(folder_name or "reel")
        output_dir = base_output / slug
        output_dir.mkdir(parents=True, exist_ok=True)
        final_output_dir = None
        print(f"[Output] Folder: {output_dir}")
    voiceover_on = not args.no_voiceover
    use_videos = args.video_gen

    # Phase 1 (Scene Planning + Overlay Planner)
    num_scenes = getattr(args, "scenes", None)
    duration_per_scene = None
    if num_scenes and args.length:
        duration_per_scene = args.length // num_scenes

    if args.plan:
        plan = load_scene_plan(args.plan)
        print(f"[Phase 1] Loaded plan: {args.plan}")
        if args.assemble_only:
            output_dir = args.plan.parent
            write_dir = base_output / _slugify(args.name) if args.name else output_dir
            voiceover_path = output_dir / "voiceover.wav"
            if not voiceover_path.exists():
                voiceover_path = output_dir / "voiceover.mp3"
            run_phase5_assemble(
                plan, output_dir, voiceover_path if voiceover_path.exists() else None,
                use_videos=True,
                max_duration_sec=args.length or plan.get("total_duration", 30),
                output_path=write_dir / "final.mp4",
            )
            if not args.no_caption:
                run_phase6_package(plan, write_dir / "final.mp4", write_dir)
            print("\nDone. Output:", write_dir)
            return
    else:
        plan, _ = run_phase1(
            text,
            args.length,
            voiceover_on,
            output_dir,
            num_scenes=num_scenes,
            duration_per_scene=duration_per_scene,
        )
    if args.phase == 1:
        print("\nDone. Output:", output_dir)
        return

    # Phase 2: Images for I2V
    start_end_pairs: list[tuple[Path, Path]] | None = None
    if use_videos:
        start_end_pairs = _get_or_generate_start_end_pairs(
            plan, output_dir, args.phase, getattr(args, "frames", 4)
        )
        if args.phase == 2:
            return
    else:
        run_phase2(plan, output_dir, for_video_gen=False)
        if args.phase == 2:
            return

    # Phase 3: Voiceover (Gemini TTS - free tier)
    voiceover_path = run_phase3(plan, voiceover_on, output_dir)
    if args.phase == 3:
        return

    # Phase 4: Video gen (Wan / Replicate / Grok)
    if use_videos:
        run_phase4_video(plan, output_dir, start_end_pairs=start_end_pairs)
        if args.phase == 4:
            return
    else:
        pass

    # Phase 5: Assemble (concat + mux). Cap duration when --length specified.
    write_dir = final_output_dir or output_dir
    mp4_path = run_phase5_assemble(
        plan, output_dir, voiceover_path, use_videos,
        max_duration_sec=args.length,
        output_path=write_dir / "final.mp4",
    )
    if args.phase == 5:
        print("\nDone. Output:", write_dir)
        return

    # Phase 6: Packaging (optional)
    if not args.no_caption:
        run_phase6_package(plan, mp4_path, write_dir)
    else:
        print("[Phase 6] Skipped (--no-caption)")

    print("\nDone. Output:", write_dir)


if __name__ == "__main__":
    main()
