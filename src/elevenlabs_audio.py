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
    def generate_audio(self, text, output_file="temp_audio.mp3"):
        print(f"[ElevenLabs] Generating audio | voice: {self.voice_id} | model: {self.model_id}")

        try:
            # Primary path: generate audio via timestamped endpoint
            response = self.client.text_to_speech.convert_with_timestamps(
                voice_id=self.voice_id,
                text=text,
                model_id=self.model_id,
                output_format="mp3_44100_128",
            )
            audio_bytes = base64.b64decode(response.audio_base64)

        except Exception as exc:
            # Fallback: plain generation
            print(f"[ElevenLabs] Timestamped generation failed ({exc}). Falling back to plain mode...")
            audio_stream = self.client.text_to_speech.convert(
                voice_id=self.voice_id,
                text=text,
                model_id=self.model_id,
                output_format="mp3_44100_128",
            )
            audio_bytes = b"".join(audio_stream)

        with open(output_file, "wb") as f:
            f.write(audio_bytes)

        print(f"[ElevenLabs] Done. Audio: {output_file}")
        return output_file
