import os
import json
import sys
import re
import time
from dotenv import load_dotenv

try:
    from src.wikipedia_fetcher import WikipediaFetcher
except (ImportError, ModuleNotFoundError):
    from wikipedia_fetcher import WikipediaFetcher

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

MAX_HOOK_WORDS = 16
REQUIRED_KEYWORDS = 8
AURA2_MAX_SEGMENT_CHARS = 2000
MAX_GENERATION_ATTEMPTS = 4


def _target_words(length_seconds: int) -> int:
    """Calibrated: ~240 words ≈ 82–88s at 1.22x TTS."""
    return int(int(length_seconds) * 2.85)


def _max_words(length_seconds: int) -> int:
    return int(_target_words(length_seconds) * 1.25)


def _min_words(length_seconds: int) -> int:
    return int(_target_words(length_seconds) * 0.50)


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
        self.groq_key = os.getenv("GROQ_API_KEY")
        self.groq_model = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
        self.wiki_fetcher = WikipediaFetcher()

        if not self.groq_key:
            raise ValueError("GROQ_API_KEY is missing in .env")

    def _build_prompt(self, topic, length_seconds, wiki_data=None, strict=False):
        word_count = _target_words(length_seconds)
        max_words = _max_words(length_seconds)
        min_segments = _min_segments(length_seconds)

        wiki_facts = ""
        if wiki_data and wiki_data.get("found"):
            m_title = wiki_data.get("movie_name", "")
            m_dir = wiki_data.get("director", "Unknown Director")
            m_cast = wiki_data.get("cast", "Star Cast")
            m_plot = wiki_data.get("plot", wiki_data.get("summary", ""))
            wiki_facts = f"""
## VERIFIED WIKIPEDIA MOVIE FACTS (GROUND TRUTH — USE THIS ACCURATE DATA):
- Movie Title: {m_title}
- Verified Director: {m_dir}
- Verified Cast / Stars: {m_cast}
- True Plot / Story: {m_plot}

IMPORTANT: Write the script based directly on the verified Wikipedia plot and cast above. Do NOT hallucinate fake storylines or actors.
"""

        integrity = """
## REVIEW INTEGRITY (NON-NEGOTIABLE):
- Provide a genuine, engaging review of the movie.
- Start with an interesting and catchy story plot that sticks with people.
- Explicitly name the director, the main cast (hero and heroine / key lead), and give a rating out of 10.
- No major spoilers without a quick warning.
""" if not strict else """
## STRICT REWRITE — previous draft violated rules:
- Keep the review punchy, accurate, and engaging.
- First tts_segment MUST be 14 words or fewer.
- Do not just narrate the plot, provide an actual review and opinion.
"""

        return f"""You are an elite YouTube movie reviewer. Write a {length_seconds}-SECOND movie review voiceover script.

TOPIC: {topic}
{wiki_facts}
HARD REQUIREMENTS (automatic rejection if violated):
- Between {int(word_count * 0.88)} and {max_words} words in `script` (target ~{word_count})
- {min_segments} or more `tts_segments` (need {min_segments}+)
- EXACTLY 8 `keywords` for background visuals
{integrity}

## STRUCTURE for {length_seconds}s:
1. HOOK & PLOT (5–15s): 2-4 segments, start with an interesting and catchy story plot based on the Wikipedia plot that hooks the viewer.
2. DIRECTOR & CAST (15–25s): 2-4 segments, mention the director and the main cast (hero and heroine / main lead).
3. RATING & CTA (last 5s): 1-2 segments, give a rating and a quick call to action.

## KEYWORDS:
- Generate EXACTLY 8 keywords that describe scenes, characters, or the poster of the movie for image search.
- Include the movie name or character name (e.g. "Inception Leonardo DiCaprio", "Baahubali waterfall fight").

## TTS SEGMENTS:
- One segment per spoken beat, 10–22 words each
- Emotions: hook, dramatic, excited, disappointed, analytical, cta
- Concatenated segment texts MUST equal the full `script`
- NO ellipses (...)

## OUTPUT (JSON ONLY):
{{
    "title": "Hook title max 58 chars",
    "hero": "Name of the main hero/actor",
    "heroine": "Name of the main heroine/actress or N/A",
    "director": "Name of the director",
    "script": "Full {word_count}-word script as one string...",
    "tts_segments": [
        {{"text": "segment 1 text here", "emotion": "hook"}},
        {{"text": "segment 2 text here", "emotion": "analytical"}}
    ],
    "keywords": ["kw1", "kw2", "kw3", "kw4", "kw5", "kw6", "kw7", "kw8"]
}}

CRITICAL: Return valid JSON only with at least {min_segments} tts_segments."""

    def _build_expand_prompt(self, topic, length_seconds, data, errors, wiki_data=None):
        word_count = _target_words(length_seconds)
        max_words = _max_words(length_seconds)
        min_words = _min_words(length_seconds)
        min_segments = _min_segments(length_seconds)
        max_seg = _max_segments(length_seconds)
        current_words = len((data.get("script") or "").split())
        current_segments = len(data.get("tts_segments") or [])
        prev_script = (data.get("script") or "")[:500]

        wiki_facts = ""
        if wiki_data and wiki_data.get("found"):
            wiki_facts = f"Wikipedia Ground Truth: {wiki_data.get('plot', '')[:300]}..."

        return f"""REJECTED — your previous script did NOT meet length requirements for a {length_seconds}-second video.

Errors: {errors}
Previous draft: {current_words} words, {current_segments} segments
REQUIRED: {min_words}–{max_words} words, {min_segments}+ tts_segments

TOPIC: {topic}
{wiki_facts}

Rewrite from scratch. Target ~{word_count} words total — do NOT exceed {max_words} words.
The HIGHLIGHTS section needs enough segments with opinions and facts, but stay within the word limit.

Previous script start (DO NOT reuse verbatim — EXPAND):
{prev_script}...

Return JSON only with title, hero, heroine, director, script ({min_words}–{max_words} words), {min_segments}–{max_seg} tts_segments, 8 keywords."""

    def _build_trim_prompt(self, topic, length_seconds, data, errors, wiki_data=None):
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

        if not data.get("hero"):
            errors.append("missing hero/actor name")
        if not data.get("director"):
            errors.append("missing director name")

        return errors

    def _parse_response(self, text, wiki_data=None):
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

        # Auto-compute script if missing or list
        script_val = data.get("script") or ""
        if isinstance(script_val, list):
            script_val = " ".join(str(x) for x in script_val).strip()
        elif not script_val and tts_segments:
            script_val = " ".join((s.get("text") or "").strip() for s in tts_segments if (s.get("text") or "").strip())
        data["script"] = script_val

        # Auto-fill metadata from Wikipedia if missing
        if wiki_data and wiki_data.get("found"):
            if not data.get("director") and wiki_data.get("director"):
                data["director"] = wiki_data["director"]
            if not data.get("hero") and wiki_data.get("hero_hint"):
                data["hero"] = wiki_data["hero_hint"]
            if not data.get("heroine"):
                data["heroine"] = wiki_data.get("heroine_hint") or "N/A"

        # Defaults for hero/heroine/director
        if not data.get("hero"):
            data["hero"] = "Lead Actor"
        if not data.get("heroine"):
            data["heroine"] = "N/A"
        if not data.get("director"):
            data["director"] = "Director"

        # Ensure keywords list has exactly 8 items
        kw = data.get("keywords") or []
        if not isinstance(kw, list):
            kw = []
        base_name = wiki_data.get("movie_name", "Movie") if wiki_data else "Movie"
        fallback_kws = [
            f"{base_name} official poster",
            f"{base_name} main character",
            f"{base_name} iconic scene",
            f"{base_name} climax action",
            f"{base_name} cinematic still",
            f"{base_name} movie dialogue",
            f"{base_name} emotional moment",
            f"{base_name} ending scene",
        ]
        while len(kw) < REQUIRED_KEYWORDS:
            kw.append(fallback_kws[len(kw)])
        if len(kw) > REQUIRED_KEYWORDS:
            kw = kw[:REQUIRED_KEYWORDS]
        data["keywords"] = kw

        return data["script"], data["keywords"], data.get("title", ""), tts_segments, data

    def _call_groq(self, prompt):
        from openai import OpenAI
        client = OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=self.groq_key,
        )

        models_to_try = [self.groq_model]
        # Common models on Groq
        for alt in ["qwen/qwen3.8-27b", "llama-3.3-70b-versatile"]:
            if alt not in models_to_try:
                models_to_try.append(alt)

        last_err = None
        for model in models_to_try:
            for attempt in range(2):
                try:
                    response = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.85,
                        max_tokens=900,
                    )
                    content = response.choices[0].message.content
                    if content and content.strip():
                        return content
                except Exception as e:
                    last_err = e
                    err_str = str(e).lower()
                    if "429" in err_str or "rate_limit" in err_str or "tokens" in err_str:
                        print(f"[ScriptGen] Groq rate limit on {model}, backing off 3s...")
                        time.sleep(3)
                        continue
                    break

        raise RuntimeError(f"Groq completions failed: {last_err}")

    def generate_script(self, topic, length_seconds=45):
        """Generates script using Groq grounded in Wikipedia movie facts."""
        print(f"Generating script via Groq for topic: '{topic}' (target {length_seconds}s)...")
        target = _target_words(length_seconds)
        min_seg = _min_segments(length_seconds)
        print(f"[ScriptGen] Target: ~{target} words, {min_seg}+ segments")

        # 1. Fetch Wikipedia metadata
        print(f"[ScriptGen] Grounding script with Wikipedia movie details...")
        wiki_data = self.wiki_fetcher.fetch_movie_details(topic)
        if wiki_data.get("found"):
            print(
                f"[ScriptGen] [OK] Wikipedia Match: '{wiki_data.get('page_title')}' | "
                f"Director: '{wiki_data.get('director')}' | Cast: '{wiki_data.get('cast')[:60]}...'"
            )
        else:
            print("[ScriptGen] [!] Movie not found on Wikipedia. Proceeding with general knowledge.")

        last_data = None
        last_result = None
        errors: list[str] = []

        for attempt in range(MAX_GENERATION_ATTEMPTS):
            if attempt == 0:
                prompt = self._build_prompt(topic, length_seconds, wiki_data=wiki_data)
            elif any("too long" in e or "too many" in e for e in errors):
                prompt = self._build_trim_prompt(topic, length_seconds, last_data, errors, wiki_data=wiki_data)
            elif any("too short" in e for e in errors):
                prompt = self._build_expand_prompt(topic, length_seconds, last_data, errors, wiki_data=wiki_data)
            else:
                prompt = self._build_prompt(topic, length_seconds, wiki_data=wiki_data, strict=True)

            try:
                raw = self._call_groq(prompt)
                script, keywords, title, tts_segments, data = self._parse_response(raw, wiki_data=wiki_data)
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
                    f"[ScriptGen] OK - {len(tts_segments)} segments, "
                    f"{spoken} spoken words (~{length_seconds}s expected)"
                )
                return script, keywords, title, tts_segments, data

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
        topic = os.getenv("VIDEO_TOPIC", "Review of the movie Inception (2010)")
        length = int(os.getenv("VIDEO_LENGTH_SECONDS", "30"))
        script, keywords, title, tts_segments, data = generator.generate_script(topic, length_seconds=length)
        print("\n--- GENERATED SCRIPT ---")
        print(script)
        print("\n--- TITLE ---")
        print(title)
        print(f"\n--- STATS: {len(tts_segments)} segments, {len(script.split())} words ---")
        print("\n--- CAST ---")
        print(f"Hero: {data.get('hero')} | Heroine: {data.get('heroine')} | Director: {data.get('director')}")
        print("\n--- SCENES/KEYWORDS ---")
        print(keywords)
    except Exception as e:
        print(f"Error: {e}")
