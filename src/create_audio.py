"""
Edge TTS Audio Generator
========================
Uses Microsoft Edge TTS (free, no API key required).

Configuration (via .env or environment variables):
  EDGE_VOICE    = "ko-KR-HyunsuMultilingualNeural"   # Multilingual neural voice
  MAX_RETRIES   = 3                                    # Retry count on network failures
  VOLUME_BOOST  = "+50%"                              # Amplify voice volume (change to +100% if still low)

Force IPv4:
  All outbound TTS requests are forced through IPv4 sockets to prevent
  IPv6 connectivity issues in CI/CD environments (Jenkins, Docker, etc.).

No TTS fallbacks — Edge TTS is the sole audio engine.
"""

import os
import asyncio
import socket
import edge_tts
from dotenv import load_dotenv

# ── Force IPv4 for all stdlib socket connections ──────────────────────────────
# Monkey-patching getaddrinfo so that asyncio / edge-tts always resolves to an
# IPv4 address. This prevents "Network unreachable" errors in environments where
# IPv6 is not properly routed (e.g. Jenkins agents, Docker containers, WSL).
_original_getaddrinfo = socket.getaddrinfo

def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

socket.getaddrinfo = _ipv4_getaddrinfo
# ─────────────────────────────────────────────────────────────────────────────


# ── Configuration constants ───────────────────────────────────────────────────
EDGE_VOICE   = "ko-KR-HyunsuMultilingualNeural"  # Multilingual neural voice
MAX_RETRIES  = 3
VOLUME_BOOST = "+50%"   # Change to +100% if still low
# ─────────────────────────────────────────────────────────────────────────────


class AudioGenerator:
    """
    Generates voiceover audio exclusively using Microsoft Edge TTS.
    No API key required. No fallback engines.
    """

    def __init__(self):
        load_dotenv()
        # Allow .env override but default to the constant above
        self.voice  = os.getenv("EDGE_VOICE", EDGE_VOICE)
        self.volume = os.getenv("VOLUME_BOOST", VOLUME_BOOST)
        self.retries = int(os.getenv("MAX_RETRIES", str(MAX_RETRIES)))

    async def _generate_audio_async(self, text: str, output_file: str):
        """Core async TTS call with retry logic."""
        print(f"[EdgeTTS] Voice : {self.voice}")
        print(f"[EdgeTTS] Volume: {self.volume}")
        print(f"[EdgeTTS] Text  : {text[:80]}...")

        for attempt in range(1, self.retries + 1):
            try:
                communicate = edge_tts.Communicate(
                    text,
                    self.voice,
                    rate="-10%",          # Slightly slower for better clarity
                    volume=self.volume,   # Apply volume boost
                )

                with open(output_file, "wb") as f:
                    async for chunk in communicate.stream():
                        if chunk["type"] == "audio":
                            f.write(chunk["data"])

                # Validate: non-empty file signals success
                if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                    print(f"[EdgeTTS] OK Audio saved to '{output_file}' "
                          f"({os.path.getsize(output_file):,} bytes)")
                    return
                else:
                    raise RuntimeError("Edge TTS returned an empty audio file.")

            except Exception as exc:
                print(f"[EdgeTTS] X Attempt {attempt}/{self.retries} failed: {exc}")
                if attempt == self.retries:
                    raise RuntimeError(
                        f"Edge TTS failed after {self.retries} attempts. "
                        "Check your internet connection and voice name."
                    ) from exc
                wait = 2 * attempt   # Back-off: 2s, 4s, …
                print(f"[EdgeTTS] Retrying in {wait}s...")
                await asyncio.sleep(wait)

    def generate_audio(self, text: str, output_file: str = "temp/temp_audio.mp3") -> str:
        """
        Public entry point — runs the async TTS call synchronously.

        Args:
            text:        The script text to synthesise.
            output_file: Destination MP3 path.

        Returns:
            Absolute path to the generated audio file.

        Raises:
            RuntimeError: If Edge TTS fails after all retries.
        """
        asyncio.run(self._generate_audio_async(text, output_file))

        if not os.path.exists(output_file) or os.path.getsize(output_file) == 0:
            raise FileNotFoundError(
                f"[EdgeTTS] Audio generation failed — '{output_file}' is missing or empty."
            )

        return output_file


# ── Quick smoke-test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    gen = AudioGenerator()
    test_text = (
        "Did you know that the human brain can process images in as little as "
        "13 milliseconds? Subscribe for more incredible facts!"
    )
    out = gen.generate_audio(test_text, "test_audio.mp3")
    print(f"[Test] Generated: {out}")
