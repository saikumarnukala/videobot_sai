"""
Build a side-by-side-style preview: alternating Pexels + Archive.org clips
with source labels so you can compare hybrid footage quality.

Usage:
    python test_hybrid_preview.py
    python test_hybrid_preview.py --topic "ancient Rome and space history"
"""
import os
import random
import argparse
from pathlib import Path

from dotenv import load_dotenv
from moviepy import VideoFileClip, CompositeVideoClip, concatenate_videoclips

from src.media_fetcher import MediaFetcher
from src.build_video import _make_text_image_clip, TARGET_W, TARGET_H
SCENE_SECONDS = 6
OUTPUT = "output/hybrid_preview.mp4"

# History-friendly keywords — good for showing Archive.org vs Pexels
DEFAULT_KEYWORDS = [
    "ancient rome ruins cinematic",
    "roman empire historical",
    "moon landing space cinematic",
    "nasa apollo mission archive",
    "egypt pyramid desert aerial",
    "egyptian history vintage film",
    "world war documentary footage",
    "historical newsreel archive",
]


def _resize_to_portrait(clip):
    scale = max(TARGET_W / clip.w, TARGET_H / clip.h)
    clip = clip.resized(scale)
    x1 = max(0, (clip.w - TARGET_W) // 2)
    y1 = max(0, (clip.h - TARGET_H) // 2)
    return clip.cropped(x1=x1, y1=y1, width=TARGET_W, height=TARGET_H)


def _label_clip(text: str, duration: float):
    return _make_text_image_clip(
        text,
        font_size=44,
        duration=duration,
        start=0,
        max_width=960,
        y_position=120,
        text_color=(255, 255, 255, 255),
        bg_opacity=160,
        corner_radius=12,
    )


def build_preview(clips_meta: list, scene_seconds: float = SCENE_SECONDS):
    os.makedirs("output", exist_ok=True)
    processed = []

    for i, item in enumerate(clips_meta):
        path = item["path"]
        source = item["source"]
        keyword = item["keyword"]
        label = "PEXELS" if source == "pexels" else "ARCHIVE.ORG"
        print(f"Processing scene {i + 1}: {label} — {keyword}")

        try:
            clip = VideoFileClip(path)
            clip = _resize_to_portrait(clip)
            if clip.duration > scene_seconds:
                start = min(max(0, (clip.duration - scene_seconds) / 2), clip.duration - scene_seconds)
                clip = clip.subclipped(start, start + scene_seconds)
            else:
                clip = clip.with_duration(scene_seconds)

            badge = _label_clip(f"{label}\n{keyword[:40]}", clip.duration)
            if badge:
                clip = CompositeVideoClip([clip, badge])
            processed.append(clip)
        except Exception as e:
            print(f"  [!] Skipping corrupt clip: {e}")

    if not processed:
        raise RuntimeError("No valid clips to render.")

    final = concatenate_videoclips(processed, method="compose")
    print(f"Rendering preview ({final.duration:.1f}s) -> {OUTPUT}")
    final.write_videofile(
        OUTPUT,
        fps=24,
        codec="libx264",
        audio=False,
        preset="fast",
        logger=None,
    )
    for c in processed:
        c.close()
    final.close()
    return OUTPUT


def main():
    parser = argparse.ArgumentParser(description="Hybrid Pexels + Archive.org preview")
    parser.add_argument("--topic", default="ancient history and space exploration")
    parser.add_argument("--scene-seconds", type=float, default=SCENE_SECONDS)
    args = parser.parse_args()

    load_dotenv()
    os.environ["VIDEO_SOURCE"] = "hybrid"
    os.makedirs("temp", exist_ok=True)

    print("=== HYBRID MEDIA PREVIEW ===")
    print(f"Topic context: {args.topic}")
    print("Pattern: odd slots = Archive.org, even slots = Pexels\n")

    fetcher = MediaFetcher()
    keywords = DEFAULT_KEYWORDS
    clips_meta = fetcher.fetch_background_videos(keywords, min_duration=3)

    if len(clips_meta) < 4:
        raise RuntimeError(f"Only got {len(clips_meta)} clips — need at least 4 for a useful preview.")

    pexels_n = sum(1 for c in clips_meta if c["source"] == "pexels")
    archive_n = sum(1 for c in clips_meta if c["source"] == "archive")
    print(f"\nDownloaded: {pexels_n} Pexels + {archive_n} Archive.org clips")

    out = build_preview(clips_meta, scene_seconds=args.scene_seconds)
    print(f"\nDone! Open: {Path(out).resolve()}")


if __name__ == "__main__":
    main()
