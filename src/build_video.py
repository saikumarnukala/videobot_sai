import os
import math
import random
import numpy as np
import signal
import subprocess
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from moviepy import VideoFileClip, AudioFileClip, CompositeAudioClip, vfx, afx, ImageClip, CompositeVideoClip, concatenate_videoclips

# Resolve font path: use bundled font so it works on Linux (GitHub Actions) and Windows
_ASSETS_DIR = Path(__file__).parent.parent / "assets"
FONT_PATH = str(_ASSETS_DIR / "impact.ttf")

# YouTube Shorts target resolution (9:16 portrait)
TARGET_W, TARGET_H = 1080, 1920

# ──────────────────────────────────────────────────────────────────────────
#  Ken Burns cinematic zoom/pan effect
# ──────────────────────────────────────────────────────────────────────────
_KB_PRESETS = [
    {"name": "slow_zoom_in",   "start_scale": 1.0,  "end_scale": 1.15, "pan": (0, 0)},
    {"name": "slow_zoom_out",  "start_scale": 1.15, "end_scale": 1.0,  "pan": (0, 0)},
    {"name": "zoom_pan_left",  "start_scale": 1.1,  "end_scale": 1.18, "pan": (0.08, 0)},
    {"name": "zoom_pan_right", "start_scale": 1.1,  "end_scale": 1.18, "pan": (-0.08, 0)},
    {"name": "zoom_pan_up",    "start_scale": 1.05, "end_scale": 1.15, "pan": (0, 0.05)},
    {"name": "zoom_pan_down",  "start_scale": 1.05, "end_scale": 1.15, "pan": (0, -0.05)},
]


def _apply_ken_burns(clip, preset=None):
    """Apply a cinematic slow zoom/pan (Ken Burns) to the clip."""
    if preset is None:
        preset = random.choice(_KB_PRESETS)
    ss = preset["start_scale"]
    es = preset["end_scale"]
    px, py = preset["pan"]
    dur = clip.duration

    def kb_filter(get_frame, t):
        progress = t / dur if dur > 0 else 0
        scale = ss + (es - ss) * progress
        pan_x = px * progress
        pan_y = py * progress

        frame = get_frame(t)
        h, w = frame.shape[:2]

        # Calculate crop box
        new_w = int(w / scale)
        new_h = int(h / scale)
        cx = w // 2 + int(pan_x * w)
        cy = h // 2 + int(pan_y * h)

        x1 = max(0, cx - new_w // 2)
        y1 = max(0, cy - new_h // 2)
        x2 = min(w, x1 + new_w)
        y2 = min(h, y1 + new_h)
        if x2 - x1 < new_w:
            x1 = max(0, x2 - new_w)
        if y2 - y1 < new_h:
            y1 = max(0, y2 - new_h)

        cropped = frame[y1:y2, x1:x2]
        img = Image.fromarray(cropped)
        img = img.resize((w, h), Image.LANCZOS)
        return np.array(img)

    new_clip = clip.transform(kb_filter)
    return new_clip


# Helper: kill ffmpeg processes (used when Jenkins aborts the job)
def _kill_ffmpeg_processes():
    try:
        if os.name == 'nt':
            subprocess.run(['taskkill', '/F', '/T', '/IM', 'ffmpeg.exe'], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(['pkill', '-f', 'ffmpeg'], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


# Register signal handlers early so long-running renders can be interrupted cleanly
def _signal_handler(signum, frame):
    print('[VideoBuilder] Received termination signal, killing ffmpeg...', file=sys.stderr)
    _kill_ffmpeg_processes()
    sys.exit(1)

try:
    signal.signal(signal.SIGINT, _signal_handler)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, _signal_handler)
except Exception:
    # Signal support may be limited on some platforms
    pass


# ──────────────────────────────────────────────────────────────────────────
#  Resize & loop helpers
# ──────────────────────────────────────────────────────────────────────────

def _resize_to_portrait(clip):
    """Crop-scale any clip to exactly 1080×1920 regardless of source resolution."""
    scale = max(TARGET_W / clip.w, TARGET_H / clip.h)
    clip = clip.resized(scale)
    x1 = (clip.w - TARGET_W) / 2
    y1 = (clip.h - TARGET_H) / 2
    return clip.cropped(x1=x1, y1=y1, width=TARGET_W, height=TARGET_H)


def _loop_to_duration(clip, duration):
    """Reliably loop a clip to the required duration (vfx.Loop is unreliable in moviepy v2)."""
    if clip.duration >= duration:
        return clip.subclipped(0, duration)
    n = math.ceil(duration / clip.duration)
    return concatenate_videoclips([clip] * n).subclipped(0, duration)


# ──────────────────────────────────────────────────────────────────────────
#  Text rendering (subtitles, CTA, hook)
# ──────────────────────────────────────────────────────────────────────────

def _make_text_image_clip(text, font_size, duration, start, max_width, y_position,
                           text_color=(255, 255, 255, 255), bg_opacity=160,
                           corner_radius=18):
    """
    Render text to a PIL RGBA image and return a positioned moviepy ImageClip.
    Uses the bundled Impact font. Works on all platforms without ImageMagick.
    Rounded semi-transparent dark pill behind the text for a modern look.
    """
    stroke_width = max(2, font_size // 14)
    padding_x, padding_y = 32, 16

    try:
        font = ImageFont.truetype(FONT_PATH, font_size)
    except Exception:
        font = ImageFont.load_default()

    # Measure text to determine canvas size (wrap at max_width)
    dummy = Image.new("RGBA", (1, 1))
    draw_dummy = ImageDraw.Draw(dummy)

    # Word-wrap manually
    words = text.split()
    lines = []
    current_line = []
    for word in words:
        test_line = ' '.join(current_line + [word])
        bbox = draw_dummy.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] <= max_width - padding_x * 2:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
    if current_line:
        lines.append(' '.join(current_line))

    # Calculate total image dimensions
    line_heights = []
    line_widths = []
    for line in lines:
        bbox = draw_dummy.textbbox((0, 0), line, font=font)
        line_widths.append(bbox[2] - bbox[0])
        line_heights.append(bbox[3] - bbox[1])

    line_spacing = int(font_size * 0.25)
    total_text_h = sum(line_heights) + line_spacing * (len(lines) - 1)
    total_text_w = max(line_widths) if line_widths else max_width

    img_w = min(total_text_w + padding_x * 2 + stroke_width * 2, TARGET_W)
    img_h = total_text_h + padding_y * 2 + stroke_width * 2

    img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Rounded rectangle background pill
    draw.rounded_rectangle(
        [(0, 0), (img_w - 1, img_h - 1)],
        radius=corner_radius,
        fill=(0, 0, 0, bg_opacity),
    )

    # Draw each line centred
    y_cursor = padding_y + stroke_width
    for line, lw, lh in zip(lines, line_widths, line_heights):
        x = (img_w - lw) // 2
        # Stroke (black outline for readability)
        for dx in range(-stroke_width, stroke_width + 1):
            for dy in range(-stroke_width, stroke_width + 1):
                if dx == 0 and dy == 0:
                    continue
                draw.text((x + dx, y_cursor + dy), line, font=font, fill=(0, 0, 0, 255))
        # Main text
        draw.text((x, y_cursor), line, font=font, fill=text_color)
        y_cursor += lh + line_spacing

    # Centre the image horizontally on the 1080-wide frame
    x_pos = (TARGET_W - img_w) // 2
    y_pos = min(y_position, TARGET_H - img_h)

    frame = np.array(img)
    clip = (
        ImageClip(frame, is_mask=False)
        .with_position((x_pos, y_pos))
        .with_start(start)
        .with_duration(duration)
    )
    return clip


def _make_subtitle_clips(script_text, audio_duration):
    """
    Generate word-group subtitle overlays synced across the audio duration.
    Shows 4-6 words at a time in the lower-center of the screen.
    """
    words = script_text.split()
    if not words:
        return []

    WORDS_PER_GROUP = 5
    groups = []
    for i in range(0, len(words), WORDS_PER_GROUP):
        groups.append(" ".join(words[i:i + WORDS_PER_GROUP]))

    time_per_group = audio_duration / len(groups)
    clips = []
    for idx, group_text in enumerate(groups):
        start = idx * time_per_group
        dur = time_per_group
        clip = _make_text_image_clip(
            group_text.upper(),
            font_size=54,
            duration=dur,
            start=start,
            max_width=960,
            y_position=int(TARGET_H * 0.72),
            text_color=(255, 255, 255, 255),
            bg_opacity=180,
            corner_radius=14,
        )
        clips.append(clip)
    return clips


# ──────────────────────────────────────────────────────────────────────────
#  Main video builder
# ──────────────────────────────────────────────────────────────────────────

class VideoBuilder:
    def __init__(self):
        pass

    def build_final_video(self, video_paths: list, audio_path: str,
                          output_path="final_short.mp4", script_text: str = ""):
        print(f"Loading {len(video_paths)} background clips...")
        print(f"Loading main audio: {audio_path}")

        audio_clip = AudioFileClip(audio_path)
        audio_duration = audio_clip.duration

        # ── 1. Process Background Videos ────────────────────────────────
        CROSSFADE = 0.6  # seconds of crossfade between clips

        # Load clips, skipping any that are corrupted/unreadable
        loaded_clips = []
        for path in video_paths:
            try:
                clip = VideoFileClip(path)
                loaded_clips.append(clip)
            except Exception as e:
                print(f"[!] Skipping corrupt/unreadable clip: {path} ({e})")

        if not loaded_clips:
            raise RuntimeError("No valid background clips could be loaded. Cannot build video.")

        n_clips = len(loaded_clips)
        time_per_clip = audio_duration / n_clips + CROSSFADE

        # Shuffle Ken Burns presets so consecutive clips get different effects
        kb_presets = _KB_PRESETS.copy()
        random.shuffle(kb_presets)

        processed_video_clips = []
        for i, clip in enumerate(loaded_clips):
            clip = _resize_to_portrait(clip)
            clip = _loop_to_duration(clip, time_per_clip)
            # Apply cinematic Ken Burns zoom/pan
            preset = kb_presets[i % len(kb_presets)]
            clip = _apply_ken_burns(clip, preset)
            print(f"  Scene {i+1}: Ken Burns '{preset['name']}' applied")
            processed_video_clips.append(clip)

        # Concatenate with crossfade transitions
        print("Concatenating background scenes with crossfade transitions...")
        if len(processed_video_clips) > 1:
            background_clip = concatenate_videoclips(
                processed_video_clips, method="compose", padding=-CROSSFADE
            )
        else:
            background_clip = processed_video_clips[0]

        # Trim to exact audio duration
        if background_clip.duration > audio_duration:
            background_clip = background_clip.subclipped(0, audio_duration)

        # ── 2. Process Audio (Voiceover + Background Music) ─────────────
        bgm_path = "temp/bg_music.mp3"
        final_audio = audio_clip
        if os.path.exists(bgm_path):
            print(f"Mixing background music with voiceover...")
            bgm_volume = float(os.getenv("BGM_VOLUME", "0.10"))

            music_clip = AudioFileClip(bgm_path).with_effects([
                afx.AudioLoop(duration=audio_duration),
                afx.MultiplyVolume(bgm_volume)
            ])
            # Fade music in first 2s and out last 3s for a polished feel
            music_clip = music_clip.with_effects([
                afx.AudioFadeIn(2.0),
                afx.AudioFadeOut(3.0),
            ])
            final_audio = CompositeAudioClip([audio_clip, music_clip])

        # ── 3. Overlay layers ───────────────────────────────────────────
        final_clips = [background_clip]

        # 3a. Subtitle overlays (word-groups synced to audio)
        if script_text:
            print("Generating subtitle overlays...")
            sub_clips = _make_subtitle_clips(script_text, audio_duration)
            final_clips.extend(sub_clips)
            print(f"  {len(sub_clips)} subtitle cards generated")

        # 3b. Subscribe CTA overlay (last 3 seconds)
        cta_start = max(0, audio_duration - 3.0)
        cta_clip = _make_text_image_clip(
            "SUBSCRIBE FOR MORE",
            font_size=52,
            duration=3.0,
            start=cta_start,
            max_width=900,
            y_position=int(TARGET_H * 0.88),
            text_color=(255, 220, 0, 255),
            bg_opacity=200,
        )
        final_clips.append(cta_clip)

        # ── 4. Composite & Render ───────────────────────────────────────
        composite_video = CompositeVideoClip(
            final_clips, size=(TARGET_W, TARGET_H)
        ).with_duration(audio_duration)

        final_video = composite_video.with_audio(final_audio)

        # Use medium preset for much better quality (only ~2x slower than ultrafast)
        render_preset = os.getenv("RENDER_PRESET", "medium")
        print(f"Rendering final video (preset={render_preset}). This may take a few minutes...")
        try:
            final_video.write_videofile(
                output_path,
                fps=30,
                codec="libx264",
                audio_codec="aac",
                preset=render_preset,
                bitrate="8M",
                threads=4,
                ffmpeg_params=[
                    "-crf", "18",        # high-quality constant rate factor
                    "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart",  # web-optimised: metadata at start
                ],
            )
        except (KeyboardInterrupt, SystemExit):
            print('[VideoBuilder] Render interrupted. Killing ffmpeg and aborting.', file=sys.stderr)
            _kill_ffmpeg_processes()
            raise
        except Exception:
            # Ensure ffmpeg doesn't linger if moviepy/ffmpeg errors out
            _kill_ffmpeg_processes()
            raise

        # Cleanup
        background_clip.close()
        audio_clip.close()
        if os.path.exists(bgm_path) and 'music_clip' in dir():
            try:
                music_clip.close()
                final_audio.close()
            except Exception:
                pass
        for c in processed_video_clips:
            c.close()
        composite_video.close()

        print(f"Successfully generated final video: {output_path}")
        return output_path

if __name__ == "__main__":
    builder = VideoBuilder()
