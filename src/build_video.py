import os
import json
import math
from pathlib import Path
from moviepy import VideoFileClip, AudioFileClip, CompositeAudioClip, vfx, afx, TextClip, CompositeVideoClip, concatenate_videoclips

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
                text_clip = (
                    TextClip(
                        text=grp['text'].upper(),
                        font=FONT_PATH,
                        font_size=72,
                        color="white",
                        stroke_color="black",
                        stroke_width=5,
                        method="caption",
                        size=(900, None),
                    )
                    .with_position(("center", 0.72), relative=True)
                    .with_start(grp['start'])
                    .with_duration(grp['end'] - grp['start'])
                )
                final_clips.append(text_clip)

        # 4. Subscribe CTA overlay (last 3 seconds) — above subtitles
        cta_start = max(0, audio_duration - 3.0)
        cta_clip = (
            TextClip(
                text="⬇ SUBSCRIBE FOR MORE ⬇",
                font=FONT_PATH,
                font_size=52,
                color="yellow",
                stroke_color="black",
                stroke_width=3,
                method="caption",
                size=(900, None),
            )
            .with_position(("center", 0.88), relative=True)
            .with_start(cta_start)
            .with_duration(3.0)
        )
        final_clips.append(cta_clip)

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
