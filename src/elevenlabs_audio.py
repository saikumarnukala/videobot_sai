"""
ElevenLabs voice synthesis + voice cloning integration.

Activated automatically when ELEVENLABS_API_KEY is set in environment/GitHub secrets.

Setup guide:
  1. Sign up at https://elevenlabs.io   (free: 10,000 chars/month)
  2. To clone YOUR voice:
       - Record 2-3 minutes of yourself speaking clearly (MP3 or WAV)
       - Go to ElevenLabs → Voices → Add Voice → Instant Voice Clone
       - Upload your recording → get your Voice ID
  3. Add to GitHub Secrets:
       ELEVENLABS_API_KEY   = your API key  (Profile → API Key)
       ELEVENLABS_VOICE_ID  = your cloned voice ID
  4. That's it! The pipeline auto-switches from Edge TTS to your voice.

Plan guide (characters per month):
  Free      → 10,000  (~16 videos/month)
  Starter   → 30,000  (~50 videos/month)  $5/month
  Creator   → 100,000 (~166 videos/month) $22/month  ← recommended for daily 4x posting
"""

import os
import json
import base64


class ElevenLabsAudioGenerator:
    # Default voice: "Rachel" — professional, warm English voice (works without cloning)
    _DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"
    _DEFAULT_MODEL    = "eleven_turbo_v2_5"   # fastest + cheapest per-char model

    def __init__(self):
        self.api_key  = os.getenv("ELEVENLABS_API_KEY")
        self.voice_id = os.getenv("ELEVENLABS_VOICE_ID", self._DEFAULT_VOICE_ID)
        self.model_id = os.getenv("ELEVENLABS_MODEL_ID", self._DEFAULT_MODEL)

        from elevenlabs.client import ElevenLabs
        self.client = ElevenLabs(api_key=self.api_key)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def generate_audio_and_subs(self, text, output_file="temp_audio.mp3",
                                subtitle_file="temp_subs.json"):
        print(f"[ElevenLabs] Generating audio | voice: {self.voice_id} | model: {self.model_id}")

        try:
            # Primary path: generate audio + character-level timing in one call
            response = self.client.text_to_speech.convert_with_timestamps(
                voice_id=self.voice_id,
                text=text,
                model_id=self.model_id,
                output_format="mp3_44100_128",
            )
            audio_bytes = base64.b64decode(response.audio_base64)
            subs = self._alignment_to_word_subs(response.alignment)

        except Exception as exc:
            # Fallback: plain generation + proportional timing estimate
            print(f"[ElevenLabs] Timestamped generation failed ({exc}). Falling back to plain mode...")
            audio_stream = self.client.text_to_speech.convert(
                voice_id=self.voice_id,
                text=text,
                model_id=self.model_id,
                output_format="mp3_44100_128",
            )
            audio_bytes = b"".join(audio_stream)
            # Write first so we can read duration for estimation
            with open(output_file, "wb") as f:
                f.write(audio_bytes)
            subs = self._estimate_word_subs(text, output_file)
            with open(subtitle_file, "w", encoding="utf-8") as f:
                json.dump(subs, f)
            print(f"[ElevenLabs] Done (fallback). Audio: {output_file} | Subtitles: {len(subs)} words")
            return output_file, subtitle_file

        with open(output_file, "wb") as f:
            f.write(audio_bytes)
        with open(subtitle_file, "w", encoding="utf-8") as f:
            json.dump(subs, f)

        print(f"[ElevenLabs] Done. Audio: {output_file} | Subtitles: {len(subs)} words")
        return output_file, subtitle_file

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _alignment_to_word_subs(self, alignment):
        """Convert ElevenLabs character-level alignment → word-level subtitle entries."""
        chars  = alignment.characters
        starts = alignment.character_start_times_seconds
        ends   = alignment.character_end_times_seconds

        subs = []
        current_word = ""
        word_start   = None
        word_end     = None

        for i, char in enumerate(chars):
            if char in (" ", "\n", "\t"):
                if current_word:
                    subs.append({
                        "text":  current_word,
                        "start": round(word_start, 4),
                        "end":   round(word_end,   4),
                    })
                    current_word = ""
                    word_start   = None
            else:
                if not current_word:
                    word_start = starts[i]
                current_word += char
                word_end = ends[i]

        # Flush last word
        if current_word:
            subs.append({
                "text":  current_word,
                "start": round(word_start, 4),
                "end":   round(word_end,   4),
            })

        return subs

    def _estimate_word_subs(self, text, audio_file):
        """Proportional word timing estimate — used when alignment is unavailable."""
        from moviepy import AudioFileClip
        clip     = AudioFileClip(audio_file)
        duration = clip.duration
        clip.close()

        # Strip punctuation for display but keep ordering
        import re
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
