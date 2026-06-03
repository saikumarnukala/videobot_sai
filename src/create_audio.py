"""
Deepgram Aura-2 Audio Generator
===============================
Uses Deepgram Aura-2 TTS with emotion-aware delivery.

Aura-2 has no explicit emotion tags — it reads tone from punctuation, pacing,
and context. This module maps script emotions to per-segment speed and formats
text for natural, expressive narration.

Configuration (via .env):
  DEEPGRAM_API_KEY   = your Deepgram API key (required)
  DEEPGRAM_VOICE     = optional fixed voice (overrides daily rotation)
  DEEPGRAM_SPEED     = base speaking speed when no emotion is set (default 0.95)
  MAX_RETRIES        = retry count on network failures (default 3)

Daily voice rotation uses expressive Aura-2 English voices only.
"""

import os
import re
import time
import tempfile
from datetime import date

from dotenv import load_dotenv

# Expressive Aura-2 voices — energetic, emotional delivery for Shorts narration.
AURA2_DAILY_VOICES = [
    "aura-2-thalia-en",      # Clear, confident, energetic
    "aura-2-asteria-en",     # Knowledgeable, energetic
    "aura-2-selene-en",      # Expressive, engaging, energetic
    "aura-2-ophelia-en",     # Expressive, enthusiastic, cheerful
    "aura-2-aurora-en",      # Cheerful, expressive, energetic
    "aura-2-phoebe-en",      # Energetic, warm, casual
    "aura-2-iris-en",        # Cheerful, positive, approachable
    "aura-2-delia-en",       # Friendly, cheerful, breathy
    "aura-2-juno-en",        # Natural, engaging, melodic
    "aura-2-vesta-en",       # Natural, expressive, empathetic
    "aura-2-apollo-en",      # Confident, comfortable, casual
    "aura-2-helena-en",      # Caring, natural, positive
    "aura-2-hyperion-en",    # Caring, warm, empathetic
    "aura-2-draco-en",       # Warm, approachable, storytelling
]

# Emotion → speaking speed (Aura-2 range ~0.7–1.5). Slower = weight; faster = urgency.
EMOTION_SPEED = {
    "shock": 1.08,
    "urgency": 1.10,
    "hook": 1.06,
    "curiosity": 0.93,
    "tension": 0.90,
    "surprise": 1.04,
    "awe": 0.88,
    "inspiration": 0.94,
    "warmth": 0.92,
    "payoff": 0.93,
    "belonging": 0.95,
    "cta": 0.97,
    "hope": 0.94,
    "dramatic": 0.89,
}

DEFAULT_SPEED = 0.95
MAX_RETRIES = 3


def get_daily_voice(voices=None) -> str:
    """Return the Aura-2 model for today based on the calendar day."""
    pool = voices or AURA2_DAILY_VOICES
    if not pool:
        raise ValueError("Voice pool is empty.")
    index = date.today().toordinal() % len(pool)
    return pool[index]


def _format_for_aura(text: str, emotion: str) -> str:
    """Light post-processing so Aura-2 picks up pauses and emphasis."""
    text = text.strip()
    if not text:
        return text

    # Ensure sentence-ending punctuation (Aura-2 uses this for intonation).
    if text[-1] not in ".!?":
        if emotion in ("shock", "urgency", "hook", "surprise"):
            text += "!"
        elif emotion in ("curiosity", "tension"):
            text += "?"
        else:
            text += "."

    # Dramatic beats: add a trailing pause where the LLM didn't include one.
    if emotion in ("shock", "awe", "dramatic", "tension") and "..." not in text:
        text = text.rstrip(".!?") + "..."

    return text


def _infer_segments_from_text(text: str) -> list[dict]:
    """Fallback: split plain script into emotional beats by position."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
    if not sentences:
        return [{"text": text, "emotion": "hook"}]

    n = len(sentences)
    emotions_by_index = {
        0: "hook",
        1: "curiosity",
        2: "tension",
    }
    segments = []
    for i, sentence in enumerate(sentences):
        if i == 0:
            emotion = "hook"
        elif i == n - 1:
            emotion = "cta"
        elif i >= n - 2:
            emotion = "hope"
        elif i <= int(n * 0.35):
            emotion = emotions_by_index.get(i, "curiosity")
        elif i <= int(n * 0.75):
            emotion = "payoff" if i == int(n * 0.5) else "tension"
        else:
            emotion = "inspiration"
        segments.append({"text": sentence, "emotion": emotion})
    return segments


class AudioGenerator:
    """
    Generates emotion-aware voiceover using Deepgram Aura-2 TTS.
    Each segment is synthesised with speed tuned to its emotional beat, then stitched.
    """

    def __init__(self):
        load_dotenv()

        self.api_key = os.getenv("DEEPGRAM_API_KEY", "").strip()
        if not self.api_key:
            raise ValueError(
                "DEEPGRAM_API_KEY is not set. Add it to your .env file. "
                "Get a key at https://console.deepgram.com/"
            )

        custom_pool = os.getenv("DEEPGRAM_VOICES", "").strip()
        if custom_pool:
            self.voice_pool = [v.strip() for v in custom_pool.split(",") if v.strip()]
        else:
            self.voice_pool = AURA2_DAILY_VOICES

        fixed_voice = os.getenv("DEEPGRAM_VOICE", "").strip()
        self.voice = fixed_voice or get_daily_voice(self.voice_pool)
        self.base_speed = float(os.getenv("DEEPGRAM_SPEED", str(DEFAULT_SPEED)))
        self.retries = int(os.getenv("MAX_RETRIES", str(MAX_RETRIES)))

        from deepgram import DeepgramClient
        self.client = DeepgramClient(api_key=self.api_key)

    def _speed_for_emotion(self, emotion: str, segment_speed=None) -> float:
        if segment_speed is not None:
            return float(segment_speed)
        return EMOTION_SPEED.get((emotion or "").lower(), self.base_speed)

    def _synthesise_segment(self, text: str, speed: float) -> bytes:
        response = self.client.speak.v1.audio.generate(
            text=text,
            model=self.voice,
            encoding="mp3",
            speed=speed,
        )
        audio_bytes = b"".join(response)
        if not audio_bytes:
            raise RuntimeError("Deepgram returned empty audio data.")
        return audio_bytes

    def _generate_segment_with_retry(self, text: str, speed: float) -> bytes:
        for attempt in range(1, self.retries + 1):
            try:
                return self._synthesise_segment(text, speed)
            except Exception as exc:
                print(f"[Deepgram] X Segment attempt {attempt}/{self.retries} failed: {exc}")
                if attempt == self.retries:
                    raise
                time.sleep(2 * attempt)
        raise RuntimeError("Unreachable")

    def _concat_mp3_segments(self, segment_bytes_list: list[bytes], output_file: str):
        from pydub import AudioSegment

        combined = AudioSegment.empty()
        for chunk in segment_bytes_list:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp.write(chunk)
                tmp_path = tmp.name
            try:
                combined += AudioSegment.from_mp3(tmp_path)
            finally:
                os.remove(tmp_path)

        os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
        combined.export(output_file, format="mp3", bitrate="128k")

    def generate_audio(
        self,
        text: str,
        output_file: str = "temp/temp_audio.mp3",
        tts_segments: list | None = None,
    ) -> str:
        """
        Generate MP3 voiceover with emotion-aware pacing.

        Args:
            text:          Full script (used for fallback segmentation).
            output_file:   Destination MP3 path.
            tts_segments:  Optional list of {"text", "emotion", "speed"?} dicts from ScriptGenerator.

        Returns:
            Path to the generated audio file.
        """
        segments = tts_segments or _infer_segments_from_text(text)
        if not segments:
            segments = [{"text": text, "emotion": "hook"}]

        print(f"[Deepgram] Model    : {self.voice}")
        print(f"[Deepgram] Segments : {len(segments)} emotional beats")

        segment_audio: list[bytes] = []
        total_chars = 0

        for i, seg in enumerate(segments, 1):
            raw = (seg.get("text") or "").strip()
            if not raw:
                continue

            emotion = (seg.get("emotion") or "hook").lower()
            speed = self._speed_for_emotion(emotion, seg.get("speed"))
            tts_text = _format_for_aura(raw, emotion)
            total_chars += len(tts_text)

            if total_chars > 2000:
                print("[Deepgram] Warning: approaching Aura-2 2000-char limit; skipping remaining segments.")
                break

            print(f"[Deepgram]   [{i}] {emotion} @ {speed:.2f} — {tts_text[:60]}...")
            segment_audio.append(self._generate_segment_with_retry(tts_text, speed))

        if not segment_audio:
            raise RuntimeError("No audio segments were generated.")

        if len(segment_audio) == 1:
            os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
            with open(output_file, "wb") as f:
                f.write(segment_audio[0])
        else:
            self._concat_mp3_segments(segment_audio, output_file)

        if not os.path.exists(output_file) or os.path.getsize(output_file) == 0:
            raise FileNotFoundError(
                f"[Deepgram] Audio generation failed — '{output_file}' is missing or empty."
            )

        print(
            f"[Deepgram] OK Audio saved to '{output_file}' "
            f"({os.path.getsize(output_file):,} bytes, {len(segment_audio)} segments)"
        )
        return output_file


if __name__ == "__main__":
    gen = AudioGenerator()
    test_segments = [
        {"text": "Stop everything.", "emotion": "shock"},
        {"text": "What if I told you the human brain processes images in 13 milliseconds?", "emotion": "curiosity"},
        {"text": "That's faster than you can blink.", "emotion": "awe"},
        {"text": "Follow for more mind-blowing facts.", "emotion": "cta"},
    ]
    out = gen.generate_audio("", "test_audio.mp3", tts_segments=test_segments)
    print(f"[Test] Generated: {out}")
