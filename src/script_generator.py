import os
import json
import sys
import re
from dotenv import load_dotenv

BANNED_PHRASES = [
    "harvard discovered",
    "leaked document",
    "scientists don't want you to know",
    "scientists hide",
    "doctors don't want",
    "they don't want you to know",
    "what the government hides",
    "billionaires don't want",
]

MAX_HOOK_WORDS = 12
REQUIRED_KEYWORDS = 8
AURA2_MAX_SEGMENT_CHARS = 2000
MAX_GENERATION_ATTEMPTS = 4


def _target_words(length_seconds: int) -> int:
    """Calibrated: ~240 words ≈ 82–88s at 1.22x TTS."""
    return int(int(length_seconds) * 2.85)


def _max_words(length_seconds: int) -> int:
    return int(_target_words(length_seconds) * 1.03)


def _min_words(length_seconds: int) -> int:
    return int(_target_words(length_seconds) * 0.88)


def _max_segments(length_seconds: int) -> int:
    return max(22, int(int(length_seconds) // 3.0))


def _min_segments(length_seconds: int) -> int:
    return max(8, int(int(length_seconds) // 3.5))


def _segment_word_count(segments: list) -> int:
    return sum(len((s.get("text") or "").split()) for s in segments)


def _trim_segments_to_word_count(segments: list, max_words: int) -> list:
    """Remove middle segments until spoken word count is within budget."""
    segs = [dict(s) for s in segments]
    while _segment_word_count(segs) > max_words and len(segs) > 3:
        middle = list(range(1, len(segs) - 1))
        if not middle:
            break
        idx = max(middle, key=lambda i: len(segs[i].get("text", "").split()))
        segs.pop(idx)
    return segs


def _segments_to_script(segments: list) -> str:
    return " ".join((s.get("text") or "").strip() for s in segments if (s.get("text") or "").strip())


def _fit_script_to_duration(segments: list, length_seconds: int) -> tuple[str, list]:
    """Trim segment list to match target word budget for video length."""
    max_w = _max_words(length_seconds)
    min_w = _min_words(length_seconds)
    segs = _trim_segments_to_word_count(segments, max_w)
    spoken = _segment_word_count(segs)
    if spoken < min_w:
        return _segments_to_script(segments), segments
    return _segments_to_script(segs), segs


class ScriptGenerator:
    def __init__(self):
        load_dotenv()
        self.groq_key   = os.getenv("GROQ_API_KEY")
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

        if not self.groq_key:
            raise ValueError("GROQ_API_KEY is missing in .env")

    def _build_prompt(self, topic, length_seconds, strict=False):
        word_count = _target_words(length_seconds)
        max_words = _max_words(length_seconds)
        min_segments = _min_segments(length_seconds)
        integrity = """
## FACTUAL INTEGRITY (NON-NEGOTIABLE):
- Only use plausible, general-knowledge claims — NO fake studies, universities, or "leaked documents"
- Never say "Harvard discovered", "scientists hide this", or "they don't want you to know"
- Prefer concrete specifics over vague hype ("octopus has three hearts" > "scientists are shocked")
- If uncertain, use framing like "Here's something most people miss about {topic}..."
""" if not strict else """
## STRICT REWRITE — previous draft violated rules:
- Remove ALL fake authority claims and fabricated statistics
- Keep the hook punchy but honest — curiosity without deception
- First tts_segment MUST be 12 words or fewer
"""

        return f"""You are an elite YouTube scriptwriter. Write a {length_seconds}-SECOND voiceover script.

TOPIC: {topic}
HARD REQUIREMENTS (automatic rejection if violated):
- Between {int(word_count * 0.88)} and {max_words} words in `script` (target ~{word_count})
- {min_segments} or more `tts_segments` (NOT 5, NOT 8 — need {min_segments}+)
- EXACTLY 8 `keywords`
{integrity}

## STRUCTURE for {length_seconds}s:
1. HOOK (3–5s): 1 segment, max 12 words, emotion=shock/hook
2. CURIOSITY STACK (5–30s): 5–7 segments building open loops
3. DEEP DIVE (30–{length_seconds - 10}s): 10–14 segments — examples, facts, twists (LONGEST section)
4. CTA (last 5–8s): 2 segments, emotion=cta/hope

## TTS SEGMENTS:
- One segment per spoken beat, 10–22 words each
- Emotions: shock, urgency, hook, curiosity, tension, surprise, awe, inspiration, warmth, payoff, belonging, cta, hope, dramatic
- Concatenated segment texts MUST equal the full `script`
- NO ellipses (...)

## OUTPUT (JSON ONLY — do NOT copy a short example; you need {min_segments}+ segments):
{{
    "title": "Hook title max 58 chars",
    "script": "Full {word_count}-word script as one string...",
    "tts_segments": [
        {{"text": "segment 1 text here", "emotion": "shock"}},
        {{"text": "segment 2 text here", "emotion": "curiosity"}}
    ],
    "keywords": ["kw1", "kw2", "kw3", "kw4", "kw5", "kw6", "kw7", "kw8"]
}}

CRITICAL: Your `tts_segments` array MUST contain at least {min_segments} entries. Count before responding."""

    def _build_expand_prompt(self, topic, length_seconds, data, errors):
        word_count = _target_words(length_seconds)
        max_words = _max_words(length_seconds)
        min_words = _min_words(length_seconds)
        min_segments = _min_segments(length_seconds)
        max_seg = _max_segments(length_seconds)
        current_words = len((data.get("script") or "").split())
        current_segments = len(data.get("tts_segments") or [])
        prev_script = (data.get("script") or "")[:500]

        return f"""REJECTED — your previous script did NOT meet length requirements for a {length_seconds}-second video.

Errors: {errors}
Previous draft: {current_words} words, {current_segments} segments
REQUIRED: {min_words}–{max_words} words, {min_segments}+ tts_segments

TOPIC: {topic}

Rewrite from scratch. Target ~{word_count} words total — do NOT exceed {max_words} words.
The DEEP DIVE section needs 10–14 segments with facts and examples, but stay within the word limit.

Previous script start (DO NOT reuse verbatim — EXPAND):
{prev_script}...

Return JSON only with title, script ({min_words}–{max_words} words), {min_segments}–{max_seg} tts_segments, 8 keywords."""

    def _build_trim_prompt(self, topic, length_seconds, data, errors):
        min_words = _min_words(length_seconds)
        max_words = _max_words(length_seconds)
        min_segments = _min_segments(length_seconds)
        max_seg = _max_segments(length_seconds)
        current_words = len((data.get("script") or "").split())
        prev_script = (data.get("script") or "")[:800]

        return f"""REJECTED — script TOO LONG for a {length_seconds}-second video.

Errors: {errors}
Current: {current_words} words (max allowed: {max_words})

TOPIC: {topic}

Shorten the script to {min_words}–{max_words} words and {min_segments}–{max_seg} tts_segments.
Keep the hook and best facts; cut repetition and filler. Same JSON format.

Previous script (trim this down):
{prev_script}...
"""

    def _validate(self, data, length_seconds):
        errors = []
        script_raw = data.get("script") or ""
        if isinstance(script_raw, list):
            script = " ".join(str(x) for x in script_raw).strip()
        else:
            script = str(script_raw).strip()
        keywords = data.get("keywords") or []
        segments = data.get("tts_segments") or []
        title = (data.get("title") or "").strip()
        min_w = _min_words(length_seconds)
        max_w = _max_words(length_seconds)
        min_seg = _min_segments(length_seconds)

        if not script:
            errors.append("empty script")
        if not title:
            errors.append("empty title")
        if len(keywords) != REQUIRED_KEYWORDS:
            errors.append(f"need {REQUIRED_KEYWORDS} keywords, got {len(keywords)}")
        if len(segments) < min_seg:
            errors.append(f"need at least {min_seg} tts_segments, got {len(segments)}")

        if segments:
            hook_words = len(segments[0].get("text", "").split())
            if hook_words > MAX_HOOK_WORDS:
                errors.append(f"hook too long ({hook_words} words, max {MAX_HOOK_WORDS})")

        combined = " ".join(script.lower().split())
        for phrase in BANNED_PHRASES:
            if phrase in combined:
                errors.append(f"banned phrase: '{phrase}'")

        script_words = len(script.split())
        segment_words = _segment_word_count(segments)
        spoken_words = max(script_words, segment_words)

        if spoken_words < min_w:
            errors.append(
                f"too short ({spoken_words} spoken words, need {min_w}–{max_w} for {length_seconds}s)"
            )
        if spoken_words > max_w:
            errors.append(
                f"too long ({spoken_words} spoken words, need {min_w}–{max_w} for {length_seconds}s)"
            )

        return errors

    def _parse_response(self, text):
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        cleaned = "".join(
            ch for ch in text
            if ord(ch) >= 0x20 or ch in "\t\n\r"
        )

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            match = re.search(r'\{.*\}', cleaned, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
            else:
                raise e

        tts_segments = data.get("tts_segments") or []
        if tts_segments and not isinstance(tts_segments, list):
            tts_segments = []

        return data["script"], data["keywords"], data.get("title", ""), tts_segments, data

    def _call_groq(self, prompt):
        from openai import OpenAI
        client = OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=self.groq_key,
        )
        response = client.chat.completions.create(
            model=self.groq_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.85,
        )
        return response.choices[0].message.content

    def generate_script(self, topic, length_seconds=45):
        """Generates script using Groq — retries until length requirements are met."""
        print(f"Generating script via Groq for topic: '{topic}' (target {length_seconds}s)...")
        target = _target_words(length_seconds)
        min_seg = _min_segments(length_seconds)
        print(f"[ScriptGen] Target: ~{target} words, {min_seg}+ segments")

        last_data = None
        last_result = None
        errors: list[str] = []

        for attempt in range(MAX_GENERATION_ATTEMPTS):
            if attempt == 0:
                prompt = self._build_prompt(topic, length_seconds)
            elif any("too long" in e or "too many" in e for e in errors):
                prompt = self._build_trim_prompt(topic, length_seconds, last_data, errors)
            elif any("too short" in e for e in errors):
                prompt = self._build_expand_prompt(topic, length_seconds, last_data, errors)
            else:
                prompt = self._build_prompt(topic, length_seconds, strict=True)

            try:
                raw = self._call_groq(prompt)
                script, keywords, title, tts_segments, data = self._parse_response(raw)
                script, tts_segments = _fit_script_to_duration(tts_segments, length_seconds)
                data["script"] = script
                data["tts_segments"] = tts_segments
                last_data = data
                last_result = (script, keywords, title, tts_segments)
            except Exception as e:
                print(f"[ScriptGen] Groq/parse Error (attempt {attempt + 1}): {e}")
                errors = [f"parse error: {e}"]
                if attempt == MAX_GENERATION_ATTEMPTS - 1 and last_result:
                    break
                if attempt == MAX_GENERATION_ATTEMPTS - 1:
                    raise RuntimeError(f"Script generation failed via Groq: {e}") from e
                continue

            errors = self._validate(data, length_seconds)
            spoken = max(len(script.split()), _segment_word_count(tts_segments))
            if not errors:
                print(
                    f"[ScriptGen] OK — {len(tts_segments)} segments, "
                    f"{spoken} spoken words (~{length_seconds}s expected)"
                )
                return script, keywords, title, tts_segments

            print(f"[ScriptGen] Rejected (attempt {attempt + 1}/{MAX_GENERATION_ATTEMPTS}): {errors}")

        if last_result:
            spoken = max(len(last_result[0].split()), _segment_word_count(last_result[3]))
            raise RuntimeError(
                f"Could not generate a valid {length_seconds}s script after {MAX_GENERATION_ATTEMPTS} attempts. "
                f"Last draft: {spoken} words, {len(last_result[3])} segments "
                f"(need {_min_words(length_seconds)}–{_max_words(length_seconds)} words)."
            )
        raise RuntimeError(f"Script generation failed after {MAX_GENERATION_ATTEMPTS} attempts.")


if __name__ == "__main__":
    try:
        generator = ScriptGenerator()
        topic = os.getenv("VIDEO_TOPIC", "creepiest ocean facts")
        length = int(os.getenv("VIDEO_LENGTH_SECONDS", "85"))
        script, keywords, title, tts_segments = generator.generate_script(topic, length_seconds=length)
        print("\n--- GENERATED SCRIPT ---")
        print(script)
        print("\n--- TITLE ---")
        print(title)
        print(f"\n--- STATS: {len(tts_segments)} segments, {len(script.split())} words ---")
        print("\n--- SCENES/KEYWORDS ---")
        print(keywords)
    except Exception as e:
        print(f"Error: {e}")
