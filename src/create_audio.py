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
  DEEPGRAM_SPEED     = base speaking speed for Shorts (default 1.22; 1.0 = normal)
  MAX_RETRIES        = retry count on network failures (default 3)

Daily voice rotation uses expressive Aura-2 English voices only.
"""

import os
import re
import json
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

# Emotion → speaking speed for YouTube Shorts (Aura-2 range 0.7–1.5; 1.0 = normal).
# Shorts need snappy delivery — keep all values at or above 1.0.
EMOTION_SPEED = {
    "shock": 1.30,
    "urgency": 1.32,
    "hook": 1.28,
    "curiosity": 1.24,
    "tension": 1.22,
    "surprise": 1.28,
    "awe": 1.22,
    "inspiration": 1.24,
    "warmth": 1.22,
    "payoff": 1.26,
    "belonging": 1.23,
    "cta": 1.26,
    "hope": 1.24,
    "dramatic": 1.22,
}

DEFAULT_SPEED = 1.22
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

    # Shorts: avoid auto-adding "..." — Aura-2 treats it as a long pause and drags pacing.
    # Rely on ! and ? for energy; only keep ellipses if the script already includes them.

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
        # Scale emotion preset relative to user's base speed (DEEPGRAM_SPEED).
        preset = EMOTION_SPEED.get((emotion or "").lower(), self.base_speed)
        return round(min(1.5, max(0.7, preset)), 2)

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

    def _mp3_duration_seconds(self, audio_bytes: bytes) -> float:
        from pydub import AudioSegment

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        try:
            return len(AudioSegment.from_mp3(tmp_path)) / 1000.0
        finally:
            os.remove(tmp_path)

    def _concat_mp3_segments(self, segment_bytes_list: list[bytes], output_file: str) -> list[float]:
        from pydub import AudioSegment

        combined = AudioSegment.empty()
        durations: list[float] = []
        for chunk in segment_bytes_list:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp.write(chunk)
                tmp_path = tmp.name
            try:
                seg = AudioSegment.from_mp3(tmp_path)
                durations.append(len(seg) / 1000.0)
                combined += seg
            finally:
                os.remove(tmp_path)

        os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
        combined.export(output_file, format="mp3", bitrate="128k")
        return durations

    def generate_audio(
        self,
        text: str,
        output_file: str = "temp/temp_audio.mp3",
        tts_segments: list | None = None,
    ) -> tuple[str, list[dict]]:
        """
        Generate MP3 voiceover with emotion-aware pacing.

        Returns:
            Tuple of (audio path, segment timing list with start/end/duration/text/emotion).
        """
        segments = tts_segments or _infer_segments_from_text(text)
        if not segments:
            segments = [{"text": text, "emotion": "hook"}]

        print(f"[Deepgram] Model    : {self.voice}")
        print(f"[Deepgram] Segments : {len(segments)} emotional beats")

        segment_audio: list[bytes] = []
        used_segments: list[dict] = []
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
            audio_bytes = self._generate_segment_with_retry(tts_text, speed)
            segment_audio.append(audio_bytes)
            used_segments.append({"text": raw, "emotion": emotion})

        if not segment_audio:
            raise RuntimeError("No audio segments were generated.")

        if len(segment_audio) == 1:
            os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
            with open(output_file, "wb") as f:
                f.write(segment_audio[0])
            durations = [self._mp3_duration_seconds(segment_audio[0])]
        else:
            durations = self._concat_mp3_segments(segment_audio, output_file)

        if not os.path.exists(output_file) or os.path.getsize(output_file) == 0:
            raise FileNotFoundError(
                f"[Deepgram] Audio generation failed — '{output_file}' is missing or empty."
            )

        cursor = 0.0
        segment_timings = []
        for seg, dur in zip(used_segments, durations):
            segment_timings.append({
                "text": seg["text"],
                "emotion": seg["emotion"],
                "start": round(cursor, 3),
                "end": round(cursor + dur, 3),
                "duration": round(dur, 3),
            })
            cursor += dur

        timings_path = os.path.join(os.path.dirname(output_file) or ".", "segment_timings.json")
        with open(timings_path, "w", encoding="utf-8") as f:
            json.dump(segment_timings, f, indent=2)

        print(
            f"[Deepgram] OK Audio saved to '{output_file}' "
            f"({os.path.getsize(output_file):,} bytes, {len(segment_audio)} segments, {cursor:.1f}s)"
        )
        return output_file, segment_timings


if __name__ == "__main__":
    gen = AudioGenerator()
    test_segments = [
        {"text": "Stop everything.", "emotion": "shock"},
        {"text": "What if I told you the human brain processes images in 13 milliseconds?", "emotion": "curiosity"},
        {"text": "That's faster than you can blink.", "emotion": "awe"},
        {"text": "Follow for more mind-blowing facts.", "emotion": "cta"},
    ]
    out, timings = gen.generate_audio("", "test_audio.mp3", tts_segments=test_segments)
    print(f"[Test] Generated: {out} ({len(timings)} segments)")
