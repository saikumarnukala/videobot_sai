"""
FREE voice cloning using Coqui XTTS v2.
- Completely free, open-source (MIT licence)
- Clones your voice from as little as 6 seconds of reference audio
- Runs on CPU (slow, ~3-5× real-time) or GPU (fast, ~0.3× real-time)
- First run downloads the XTTS v2 model once (~1.8 GB, cached after that)

Setup (one-time, takes ~5 minutes):
  1. pip install TTS
  2. Record yourself speaking for 30–60 seconds and save as:
         assets/my_voice.wav    (or any WAV/MP3 file)
  3. Set in .env (local) or GitHub Secret (cloud):
         COQUI_VOICE_SAMPLE=assets/my_voice.wav
  4. Done — the pipeline auto-switches to your cloned voice.

For GitHub Actions:
  - Commit your voice sample file to the repo (e.g. assets/my_voice.wav)
    OR store it as a base64 secret (VOICE_SAMPLE_B64) and decode it at runtime
  - GPU runners cost more; CPU works but adds ~3-4 min to render time
  
Tip: record in a quiet room, speak the kind of sentences the bot will say.
The more varied your sample, the better the clone quality.
"""

import os
import json
import re
import tempfile


class CoquiAudioGenerator:
    _MODEL = "tts_models/multilingual/multi-dataset/xtts_v2"

    def __init__(self):
        self.voice_sample = os.getenv("COQUI_VOICE_SAMPLE", "assets/my_voice.wav")
        if not os.path.exists(self.voice_sample):
            raise FileNotFoundError(
                f"Voice sample not found: '{self.voice_sample}'. "
                "Record 30–60s of your voice, save it, and set COQUI_VOICE_SAMPLE "
                "to its path (e.g. assets/my_voice.wav)."
            )

    def _load_tts(self):
        """Lazy-load TTS so the import only happens if Coqui is actually used."""
        try:
            from TTS.api import TTS  # pip install TTS
        except ImportError:
            raise ImportError(
                "Coqui TTS is not installed. Run:  pip install TTS\n"
                "Then restart the pipeline."
            )
        print(f"[Coqui] Loading XTTS v2 model (downloads ~1.8 GB on first run)...")
        # gpu=True massively speeds this up; falls back gracefully to CPU
        tts = TTS(self._MODEL, gpu=self._has_gpu())
        return tts

    @staticmethod
    def _has_gpu() -> bool:
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False

    def generate_audio_and_subs(self, text, output_file="temp_audio.mp3",
                                subtitle_file="temp_subs.json"):
        tts = self._load_tts()

        # XTTS works best with WAV output; convert to MP3 after if needed
        if output_file.endswith(".mp3"):
            wav_file = output_file.replace(".mp3", "_raw.wav")
        else:
            wav_file = output_file

        print(f"[Coqui] Synthesising with your cloned voice (speaker: {self.voice_sample})...")
        tts.tts_to_file(
            text=text,
            speaker_wav=self.voice_sample,
            language="en",
            file_path=wav_file,
        )

        # Convert WAV → MP3 using ffmpeg (already in the pipeline)
        if wav_file != output_file:
            import subprocess
            subprocess.run(
                ["ffmpeg", "-y", "-i", wav_file, "-q:a", "2", output_file],
                check=True,
                capture_output=True,
            )
            os.remove(wav_file)

        # Build proportional word-level subtitles from audio duration
        subs = self._build_word_subs(text, output_file)
        with open(subtitle_file, "w", encoding="utf-8") as f:
            json.dump(subs, f)

        print(f"[Coqui] Done. Audio: {output_file} | Subtitles: {len(subs)} words")
        return output_file, subtitle_file

    # ------------------------------------------------------------------
    # Subtitle timing: proportional estimate based on audio duration
    # ------------------------------------------------------------------
    def _build_word_subs(self, text, audio_file):
        from moviepy import AudioFileClip
        clip     = AudioFileClip(audio_file)
        duration = clip.duration
        clip.close()

        words = [re.sub(r"[^\w'-]", "", w) for w in text.split()]
        words = [w for w in words if w]
        if not words:
            return []

        tpw = duration / len(words)
        return [
            {
                "text":  w,
                "start": round(i * tpw, 3),
                "end":   round((i + 1) * tpw, 3),
            }
            for i, w in enumerate(words)
        ]
