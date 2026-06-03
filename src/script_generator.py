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
MIN_SEGMENTS = 4
REQUIRED_KEYWORDS = 8


class ScriptGenerator:
    def __init__(self):
        load_dotenv()
        self.groq_key   = os.getenv("GROQ_API_KEY")
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

        if not self.groq_key:
            raise ValueError("GROQ_API_KEY is missing in .env")

    def _build_prompt(self, topic, length_seconds, strict=False):
        # Fast TTS (~1.22x) needs slightly more words to fill the target duration
        word_count = int(int(length_seconds) * 3.8)
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

        return f"""You are an elite YouTube Shorts scriptwriter focused on RETENTION and SHAREABILITY.
Your videos hook in under 2 seconds, deliver one clear "wow" insight, and end with a reason to follow.

TOPIC: {topic}
VIDEO LENGTH: {length_seconds} seconds (~{word_count} spoken words at fast narration pace)
{integrity}

## RETENTION STRUCTURE:

### 1. SCROLL-STOP HOOK (0–2s)
- Open with a bold question, counterintuitive fact, or "Stop —" pattern interrupt
- First tts_segment: MAX 12 words, emotion=shock or hook
- Create an information gap the viewer MUST resolve

### 2. CURIOSITY STACK (3–18s)
- 2–3 rapid beats: setup → twist → "but here's the part nobody talks about"
- Each beat = one tts_segment with matching emotion (curiosity, tension, surprise)
- Short sentences. Punchy rhythm. No filler.

### 3. PAYOFF (18–35s)
- Deliver ONE memorable insight the viewer can repeat to a friend
- Make it specific, visual, and shareable
- emotion=awe or payoff

### 4. FOLLOW CTA (last 5s)
- Natural follow prompt tied to the topic ("Follow for more [specific niche] facts")
- emotion=cta or hope — NOT generic "subscribe to my channel"

## WRITING RULES:
- Documentary narrator tone: confident, vivid, conversational
- NO "in this video", NO timestamps, NO emojis in script
- NO stage directions — spoken words only
- Every sentence must advance the story or raise stakes

## TTS SEGMENTS (Deepgram Aura-2):
Output `tts_segments`: one spoken beat per line, each with emotion tag.
Emotions: shock, urgency, hook, curiosity, tension, surprise, awe, inspiration, warmth, payoff, belonging, cta, hope, dramatic

Rules:
- 6–12 segments total covering the FULL script
- 5–18 words per segment
- Use commas for pauses; avoid ellipses (...)
- Use ! for energy, ? for curiosity
- Concatenated segment text ≈ same story as `script`

## BACKGROUND KEYWORDS (exactly 8):
1. Hook scene — dramatic, high-motion visual
2–7. Story beats — concrete visual metaphors matching each segment
8. CTA scene — inspiring forward-looking visual
Each: 3–5 words, filmable stock footage, no brands/celebrities

## OUTPUT (JSON ONLY):
{{
    "title": "Punchy hook title, max 58 chars, creates curiosity (used as on-screen hook + YouTube title)",
    "script": "Full clean script for subtitles...",
    "tts_segments": [
        {{"text": "Stop — your brain is lying to you.", "emotion": "shock"}},
        {{"text": "About {topic}, almost everyone gets this backwards.", "emotion": "curiosity"}},
        {{"text": "Here's what actually happens.", "emotion": "tension"}},
        {{"text": "One detail changes everything.", "emotion": "awe"}},
        {{"text": "Follow for more facts that hit different.", "emotion": "cta"}}
    ],
    "keywords": ["8 cinematic pexels search terms"]
}}

The title must work as a standalone hook — viewers should click even without context."""

    def _validate(self, data, length_seconds):
        errors = []
        script = (data.get("script") or "").strip()
        keywords = data.get("keywords") or []
        segments = data.get("tts_segments") or []
        title = (data.get("title") or "").strip()

        if not script:
            errors.append("empty script")
        if not title:
            errors.append("empty title")
        if len(keywords) != REQUIRED_KEYWORDS:
            errors.append(f"need {REQUIRED_KEYWORDS} keywords, got {len(keywords)}")
        if len(segments) < MIN_SEGMENTS:
            errors.append(f"need at least {MIN_SEGMENTS} tts_segments, got {len(segments)}")

        if segments:
            hook_words = len(segments[0].get("text", "").split())
            if hook_words > MAX_HOOK_WORDS:
                errors.append(f"hook too long ({hook_words} words, max {MAX_HOOK_WORDS})")

        combined = " ".join(script.lower().split())
        for phrase in BANNED_PHRASES:
            if phrase in combined:
                errors.append(f"banned phrase: '{phrase}'")

        word_count = len(script.split())
        target = int(length_seconds) * 3.8
        if word_count < target * 0.5:
            errors.append(f"script too short ({word_count} words, target ~{int(target)})")
        if word_count > target * 1.6:
            errors.append(f"script too long ({word_count} words)")

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
        """Generates script using Groq with validation and one retry."""
        print(f"Generating script via Groq for topic: '{topic}'...")

        for attempt in range(2):
            strict = attempt > 0
            prompt = self._build_prompt(topic, length_seconds, strict=strict)
            try:
                raw = self._call_groq(prompt)
                script, keywords, title, tts_segments, data = self._parse_response(raw)
            except Exception as e:
                print(f"[ScriptGen] Groq Error: {e}")
                raise RuntimeError(f"Script generation failed via Groq: {e}") from e

            errors = self._validate(data, length_seconds)
            if not errors:
                print(f"[ScriptGen] OK — {len(tts_segments)} segments, {len(script.split())} words")
                return script, keywords, title, tts_segments

            print(f"[ScriptGen] Validation failed (attempt {attempt + 1}): {errors}")
            if attempt == 1:
                print("[ScriptGen] Using last draft despite validation warnings")
                return script, keywords, title, tts_segments

        return script, keywords, title, tts_segments


if __name__ == "__main__":
    try:
        generator = ScriptGenerator()
        topic = os.getenv("VIDEO_TOPIC", "creepiest ocean facts")
        script, keywords, title, tts_segments = generator.generate_script(topic)
        print("\n--- GENERATED SCRIPT ---")
        print(script)
        print("\n--- TITLE ---")
        print(title)
        print("\n--- SCENES/KEYWORDS ---")
        print(keywords)
        print("------------------------\n")
    except Exception as e:
        print(f"Error: {e}")
