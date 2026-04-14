import os
import json
import math
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from moviepy import VideoFileClip, AudioFileClip, CompositeAudioClip, vfx, afx, ImageClip, CompositeVideoClip, concatenate_videoclips

# Resolve font path: use bundled font so it works on Linux (GitHub Actions) and Windows
_ASSETS_DIR = Path(__file__).parent.parent / "assets"
FONT_PATH = str(_ASSETS_DIR / "impact.ttf")

# YouTube Shorts target resolution (9:16 portrait)
TARGET_W, TARGET_H = 1080, 1920


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


def _make_text_image_clip(text, font_size, duration, start, max_width, y_position,
                           text_color=(255, 255, 255, 255)):
    """
    Render text to a PIL RGBA image and return a positioned moviepy ImageClip.
    Uses the bundled Impact font. Works on all platforms without ImageMagick.
    A semi-transparent dark bar is drawn behind the text for readability.
    """
    stroke_width = max(2, font_size // 16)
    padding_x, padding_y = 24, 12

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

    line_spacing = int(font_size * 0.2)
    total_text_h = sum(line_heights) + line_spacing * (len(lines) - 1)
    total_text_w = max(line_widths) if line_widths else max_width

    img_w = min(total_text_w + padding_x * 2 + stroke_width * 2, TARGET_W)
    img_h = total_text_h + padding_y * 2 + stroke_width * 2

    img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Semi-transparent dark background bar
    draw.rectangle([(0, 0), (img_w, img_h)], fill=(0, 0, 0, 160))

    # Draw each line centred
    y_cursor = padding_y + stroke_width
    for line, lw, lh in zip(lines, line_widths, line_heights):
        x = (img_w - lw) // 2
        # Stroke pass (draw text offset in 8 directions)
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
    # y_position is the top edge of the subtitle block
    # Clamp so it doesn't go off-screen
    y_pos = min(y_position, TARGET_H - img_h)

    frame = np.array(img)
    clip = (
        ImageClip(frame, is_mask=False)
        .with_position((x_pos, y_pos))
        .with_start(start)
        .with_duration(duration)
    )
    return clip


class VideoBuilder:
    def __init__(self):
        pass

    def build_final_video(self, video_paths: list, audio_path: str, subtitle_path=None, output_path="final_short.mp4"):
        print(f"Loading {len(video_paths)} background clips...")
        print(f"Loading main audio: {audio_path}")
        
        audio_clip = AudioFileClip(audio_path)
        audio_duration = audio_clip.duration
        
        # 1. Process Background Videos — resize to 1080×1920 and split evenly
        processed_video_clips = []
        time_per_clip = audio_duration / max(len(video_paths), 1)
        
        for path in video_paths:
            clip = VideoFileClip(path)
            clip = _resize_to_portrait(clip)
            clip = _loop_to_duration(clip, time_per_clip)
            processed_video_clips.append(clip)
            
        # Concatenate them all together sequentially
        print("Concatenating situational background scenes...")
        background_clip = concatenate_videoclips(processed_video_clips, method="compose")
        
        # 2. Process Audio (Voiceover + Background Music)
        bgm_path = "bg_music.mp3"
        final_audio = audio_clip
        if os.path.exists(bgm_path):
            print(f"Found {bgm_path}! Compositing background music with voiceover...")
            bgm_volume = float(os.getenv("BGM_VOLUME", "0.08"))
            
            music_clip = AudioFileClip(bgm_path).with_effects([
                afx.AudioLoop(duration=audio_duration),
                afx.MultiplyVolume(bgm_volume)
            ])
            final_audio = CompositeAudioClip([audio_clip, music_clip])
            
        # 3. Add Subtitles — bottom-centre (standard for YouTube Shorts)
        final_clips = [background_clip]
        
        if subtitle_path and os.path.exists(subtitle_path):
            print("Adding dynamic word-by-word subtitles...")
            with open(subtitle_path, 'r') as f:
                subs = json.load(f)
                
            # Filter empty entries then group into 2-word blocks
            subs = [s for s in subs if s.get('text', '').strip()]
            groups = []
            i = 0
            while i < len(subs):
                if i + 1 < len(subs):
                    grp_text = subs[i]['text'].strip() + ' ' + subs[i+1]['text'].strip()
                    grp_start = subs[i]['start']
                    grp_end = subs[i+1]['end'] + 0.05
                    i += 2
                else:
                    grp_text = subs[i]['text'].strip()
                    grp_start = subs[i]['start']
                    grp_end = subs[i]['end'] + 0.05
                    i += 1
                groups.append({'text': grp_text, 'start': grp_start, 'end': grp_end})

            for grp in groups:
                img_clip = _make_text_image_clip(
                    grp['text'].upper(),
                    font_size=72,
                    duration=grp['end'] - grp['start'],
                    start=grp['start'],
                    max_width=900,
                    y_position=int(TARGET_H * 0.72),
                )
                final_clips.append(img_clip)

        # 4. Subscribe CTA overlay (last 3 seconds) — above subtitles
        cta_start = max(0, audio_duration - 3.0)
        cta_img_clip = _make_text_image_clip(
            "SUBSCRIBE FOR MORE",
            font_size=52,
            duration=3.0,
            start=cta_start,
            max_width=900,
            y_position=int(TARGET_H * 0.88),
            text_color=(255, 220, 0, 255),
        )
        final_clips.append(cta_img_clip)

        # Force output size to 1080×1920 and duration to match audio
        composite_video = CompositeVideoClip(
            final_clips, size=(TARGET_W, TARGET_H)
        ).with_duration(audio_duration)
            
        # Apply the final mixed audio
        final_video = composite_video.with_audio(final_audio)
        
        print("Rendering final video. This may take a few minutes depending on your PC...")
        final_video.write_videofile(
            output_path, 
            fps=30, 
            codec="libx264", 
            audio_codec="aac", 
            preset="ultrafast",
            threads=4
        )
        
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
