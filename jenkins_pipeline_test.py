"""
Jenkins pipeline test script.
Tests Edge TTS with ko-KR-HyunsuMultilingualNeural voice,
Force IPv4, VOLUME_BOOST +50%, MAX_RETRIES=3.
"""

import asyncio
import socket
import os
import sys

# ── Force IPv4 ────────────────────────────────────────────────────────────────
_orig = socket.getaddrinfo
def _ipv4(host, port, family=0, type=0, proto=0, flags=0):
    return _orig(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = _ipv4
print("[IPv4] Socket patched to force IPv4")

import edge_tts

VOICE   = "ko-KR-HyunsuMultilingualNeural"
VOLUME  = "+50%"
RETRIES = 3
OUTPUT  = "jenkins_tts_test.mp3"

async def run_tts():
    text = (
        "Hello! This is a Jenkins pipeline test. "
        "Edge TTS with the Korean multilingual neural voice is working correctly. "
        "IPv4 is forced and volume boost is applied."
    )
    print(f"[TTS] Voice  : {VOICE}")
    print(f"[TTS] Volume : {VOLUME}")
    print(f"[TTS] Text   : {text[:60]}...")

    for attempt in range(1, RETRIES + 1):
        try:
            comm = edge_tts.Communicate(text, VOICE, volume=VOLUME, rate="-10%")
            with open(OUTPUT, "wb") as f:
                async for chunk in comm.stream():
                    if chunk["type"] == "audio":
                        f.write(chunk["data"])

            size = os.path.getsize(OUTPUT)
            print(f"[TTS] Audio generated: {size:,} bytes")
            assert size > 1000, "Audio file too small!"
            print("[TTS] TEST PASSED")
            return True

        except Exception as e:
            print(f"[TTS] Attempt {attempt}/{RETRIES} failed: {e}")
            if attempt == RETRIES:
                return False
            await asyncio.sleep(2 * attempt)

def check_credentials():
    keys = ["PEXELS_API_KEY", "JAMENDO_CLIENT_ID", "GROQ_API_KEY"]
    all_ok = True
    for k in keys:
        v = os.environ.get(k, "")
        if v:
            print(f"[CRED] {k}: {len(v)} chars - OK")
        else:
            print(f"[CRED] {k}: MISSING!")
            all_ok = False
    return all_ok

if __name__ == "__main__":
    print("=" * 60)
    print("JENKINS PIPELINE TEST")
    print("=" * 60)

    # 1. TTS test
    tts_ok = asyncio.run(run_tts())

    # 2. Credential check
    cred_ok = check_credentials()

    print("=" * 60)
    if tts_ok and cred_ok:
        print("ALL TESTS PASSED - Jenkins pipeline is ready!")
        sys.exit(0)
    else:
        print("SOME TESTS FAILED - check output above")
        sys.exit(1)
