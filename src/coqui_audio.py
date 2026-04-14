"""
FREE voice cloning using F5-TTS (works on Python 3.14+, CPU + GPU).
- Completely free, open-source (MIT licence)
- Zero-shot voice clone from your reference recording
- First run downloads the F5-TTS model once (~1.5 GB, cached after that)

Setup:
  1. pip install f5-tts      (already done)
  2. Record yourself: python record_voice.py  ->  assets/my_voice.wav
  3. Add to .env:  COQUI_VOICE_SAMPLE=assets/my_voice.wav
"""

import os
import json
import re


# Reference text that was read aloud during the voice recording.
# F5-TTS needs to know what was said in the reference audio.
# Override by creating assets/my_voice_ref.txt with the exact text you recorded.
_DEFAULT_REF_TEXT = (
    "Hi welcome to MindVault. Every day I bring you the most powerful ideas "
    "from science philosophy and human psychology. Did you know that the human "
    "brain can process information 20 times faster than any computer ever built. "
    "Stoic philosophers believed that the obstacle is the way. The compound effect "
    "is the most underrated force in the world. Small improvements every single day "
    "result in 37 times better outcomes after one full year. Warren Buffett made "
    "97 percent of his entire wealth after the age of 65. Thank you for watching."
)


class CoquiAudioGenerator:
    """Named CoquiAudioGenerator for create_audio.py compatibility. Uses F5-TTS internally."""

    def __init__(self):
        self.voice_sample = os.getenv("COQUI_VOICE_SAMPLE", "assets/my_voice.wav")
        if not os.path.exists(self.voice_sample):
            raise FileNotFoundError(
                f"Voice sample not found: '{self.voice_sample}'. "
                "Run record_voice.py to record your voice, then set "
                "COQUI_VOICE_SAMPLE=assets/my_voice.wav in .env"
            )
        # Load reference text from sidecar file or fall back to default
        ref_txt = os.path.splitext(self.voice_sample)[0] + "_ref.txt"
        if os.path.exists(ref_txt):
            with open(ref_txt, "r", encoding="utf-8") as fh:
                self.ref_text = fh.read().strip()
            print(f"[F5-TTS] Loaded reference text from {ref_txt}")
        else:
            self.ref_text = _DEFAULT_REF_TEXT

    def _find_ffmpeg(self):
        """Return ffmpeg path; prefers imageio-ffmpeg bundled with moviepy."""
        try:
            import imageio_ffmpeg
            path = imageio_ffmpeg.get_ffmpeg_exe()
            if path and os.path.exists(path):
                ffmpeg_dir = os.path.dirname(path)
                if ffmpeg_dir not in os.environ.get("PATH", ""):
                    os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
                return path
        except Exception:
            pass
        return "ffmpeg"

    def generate_audio_and_subs(self, text, output_file="temp_audio.mp3",
                                subtitle_file="temp_subs.json"):
        ffmpeg_bin = self._find_ffmpeg()

        try:
            from f5_tts.api import F5TTS
        except ImportError:
            raise ImportError("F5-TTS not installed. Run: pip install f5-tts")

        print("[F5-TTS] Loading model (downloads ~1.5 GB on first run)...")
        f5 = F5TTS()

        # Patch torchaudio.load to use soundfile — FFmpeg DLLs not available on this machine
        # F5-TTS calls torchaudio.load(ref_audio) internally; soundfile handles WAV without ffmpeg.
        try:
            import torchaudio, soundfile as sf, torch as _torch

            def _sf_load(path, *a, **kw):
                data, rate = sf.read(str(path), dtype="float32", always_2d=True)
                return _torch.from_numpy(data.T), rate

            torchaudio.load = _sf_load
        except Exception:
            pass  # best effort — will surface as a proper error inside infer() if it fails

        print(f"[F5-TTS] Cloning your voice for: {text[:60]}...")
        import torch
        with torch.inference_mode():
            wav, sr, _ = f5.infer(
                ref_file=self.voice_sample,
                ref_text=self.ref_text,
                gen_text=text,
                nfe_step=8,   # 8 steps: ~4x faster than 32, still good quality on CPU
                speed=1.0,
            )

        import numpy as np
        import soundfile as sf
        import subprocess

        wav_arr = np.array(wav, dtype=np.float32)
        if wav_arr.ndim > 1:
            wav_arr = wav_arr.squeeze()

        wav_file = output_file.replace(".mp3", "_raw.wav")
        sf.write(wav_file, wav_arr, sr)

        subprocess.run(
            [ffmpeg_bin, "-y", "-i", wav_file, "-q:a", "2", output_file],
            check=True, capture_output=True,
        )
        os.remove(wav_file)

        subs = self._build_word_subs(text, output_file)
        with open(subtitle_file, "w", encoding="utf-8") as f:
            json.dump(subs, f)

        print(f"[F5-TTS] Done. Audio: {output_file} | Subtitles: {len(subs)} words")
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
