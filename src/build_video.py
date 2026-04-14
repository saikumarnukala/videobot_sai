import os
import json
from pathlib import Path
from moviepy import VideoFileClip, AudioFileClip, CompositeAudioClip, vfx, afx, TextClip, CompositeVideoClip, concatenate_videoclips

# Resolve font path: use bundled font so it works on Linux (GitHub Actions) and Windows
_ASSETS_DIR = Path(__file__).parent.parent / "assets"
FONT_PATH = str(_ASSETS_DIR / "impact.ttf")

class VideoBuilder:
    def __init__(self):
        pass

    def build_final_video(self, video_paths: list, audio_path: str, subtitle_path=None, output_path="final_short.mp4"):
        print(f"Loading {len(video_paths)} background clips...")
        print(f"Loading main audio: {audio_path}")
        
        audio_clip = AudioFileClip(audio_path)
        audio_duration = audio_clip.duration
        
        # 1. Process Background Videos
        processed_video_clips = []
        time_per_clip = audio_duration / max(len(video_paths), 1)
        
        for path in video_paths:
            clip = VideoFileClip(path)
            
            # Ensure it covers the required time slice
            if clip.duration < time_per_clip:
                clip = clip.with_effects([vfx.Loop(duration=time_per_clip)])
            else:
                clip = clip.subclipped(0, time_per_clip)
                
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
            
            # Load music, loop it to match voice duration, and lower volume
            music_clip = AudioFileClip(bgm_path).with_effects([
                afx.AudioLoop(duration=audio_duration),
                afx.MultiplyVolume(bgm_volume)
            ])
            
            # Combine voice + music
            final_audio = CompositeAudioClip([audio_clip, music_clip])
            
        # 3. Add Subtitles
        final_clips = [background_clip]
        
        if subtitle_path and os.path.exists(subtitle_path):
            print("Adding dynamic word-by-word subtitles...")
            with open(subtitle_path, 'r') as f:
                subs = json.load(f)
                
            for i, sub in enumerate(subs):
                word = sub['text']
                start = sub['start']
                end = sub['end']
                
                dur = (end - start) + 0.1 
                
                text_clip = TextClip(
                    text=word.upper(),
                    font=FONT_PATH,
                    font_size=90,
                    color="white",
                    stroke_color="black",
                    stroke_width=4,
                    method="caption",
                    size=(900, None)
                ).with_position(("center", "center")).with_start(start).with_duration(dur)
                
                final_clips.append(text_clip)

        # Composite video and text
        composite_video = CompositeVideoClip(final_clips)
            
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
        for c in processed_video_clips:
            c.close()
        composite_video.close()
        
        print(f"Successfully generated final video: {output_path}")
        return output_path

if __name__ == "__main__":
    builder = VideoBuilder()
