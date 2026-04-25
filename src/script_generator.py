import os
import json
import sys
from dotenv import load_dotenv


class ScriptGenerator:
    def __init__(self):
        load_dotenv()
        # --- Groq (free, 14 400 req/day) ---
        self.groq_key   = os.getenv("GROQ_API_KEY")
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

        if not self.groq_key:
            raise ValueError("GROQ_API_KEY is missing in .env")

    # ------------------------------------------------------------------ #
    #  Shared helpers                                                      #
    # ------------------------------------------------------------------ #

    def _build_prompt(self, topic, length_seconds):
        word_count = int(length_seconds) * 3
        return f"""You are a world-class YouTube Shorts scriptwriter whose videos consistently get 10M+ views and convert 5%+ of viewers to subscribers. Your specialty is creating "unskippable" content that hooks viewers in the first 2 seconds and keeps them watching until the end.

TOPIC: {topic}
VIDEO LENGTH: {length_seconds} seconds ({word_count} words)

## UNSKIPPABLE SCRIPT STRUCTURE (FOLLOW PRECISELY):

### 1. ATOMIC HOOK (0-3 seconds) - MUST STOP THE SCROLL
- Start with a **PATTERN INTERRUPT**: shocking statistic, bold contrarian claim, or impossible question
- First sentence MUST create an "information gap" - viewer MUST watch to resolve curiosity
- Examples: "What if I told you [surprising fact about {topic}]?", "Stop everything. This changes everything about {topic}.", "97% of people get {topic} wrong. Here's why."
- **Emotional trigger**: Create urgency, shock, or FOMO (Fear Of Missing Out)

### 2. CURIOSITY STACKING (3-18 seconds) - BUILD TENSION
- Introduce 3 rapid-fire "curiosity gaps" - questions or mysteries that MUST be answered
- Use the "BUT WAIT" technique: reveal something, then add "but here's what nobody tells you"
- Include social proof: "Experts at Harvard discovered...", "A leaked document reveals..."
- **Emotional mix**: 70% curiosity, 20% surprise, 10% anticipation
- Sentence rhythm: Short. Punchy. Then a longer dramatic sentence that builds tension.

### 3. VALUE BOMB (18-32 seconds) - DELIVER THE PAYOFF
- Reveal the most valuable, shocking, or emotional insight
- Make the viewer feel: "I can't believe I didn't know this before"
- Include at least one "mind-blowing" fact that's shareable/screenshotable
- **Emotional peak**: Create awe, inspiration, or "aha moment"
- Use vivid sensory language: "Picture this...", "Imagine feeling..."

### 4. SUBSCRIBER CONVERSION (32-45 seconds) - GROW THE CHANNEL
- **Natural CTA**: Weave "follow for more" into the narrative, NOT a generic ask
- Create content promise: "Tomorrow, I'll reveal [related intriguing topic about {topic}]"
- Use "we" language to build community: "We're uncovering secrets together"
- End with a thought-provoking one-liner that lingers in the mind
- **Final emotional trigger**: Hope, belonging, or anticipation for next video

## VIRAL TECHNIQUES (MUST INCLUDE):
- **The 3-Second Rule**: If viewer isn't hooked in 3 seconds, they scroll
- **Open Loop Mastery**: Introduce mystery early, resolve late
- **Emotional Rollercoaster**: Mix curiosity -> surprise -> awe -> belonging
- **Social Currency**: Give viewer "bragging rights" knowledge to share
- **Pattern Interrupts**: Break expected YouTube patterns constantly

## WRITING STYLE:
- Write as a cinematic documentary narrator (Morgan Freeman meets action movie trailer)
- Use vivid, sensory language: "The air crackles with energy as..."
- Vary sentence length for musical rhythm
- NO filler phrases ("in this video", "today we'll talk about")
- NO stage directions, timestamps, or emojis
- ONLY spoken words - every word must earn its place

## BACKGROUND VIDEO KEYWORDS:
Generate exactly 8 cinematic background video search terms for Pexels stock footage:
1. **Hook scene** (0-3s): Dramatic, attention-grabbing visual
2-7. **Curiosity scenes** (3-32s): Visual metaphors for each curiosity gap
8. **CTA scene** (32-45s): Inspiring, forward-looking visual

Each keyword MUST be:
- Visually stunning and filmable (real footage, not abstract)
- Cinematic (drone shots, slow-motion, golden hour, macro)
- Emotionally matched to script section
- Generic enough for stock footage (no specific people/brands)
- 3-5 words, descriptive and visual

## OUTPUT FORMAT (JSON ONLY):
{{
    "script": "The full script text...",
    "keywords": ["scene1 keyword", "scene2 keyword", "scene3 keyword", "scene4 keyword", "scene5 keyword", "scene6 keyword", "scene7 keyword", "scene8 keyword"]
}}

Remember: Every viewer who finishes should think "I need to subscribe to see what's next." """

    def _parse_response(self, text):
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        data = json.loads(text.strip())
        return data["script"], data["keywords"]

    # ------------------------------------------------------------------ #
    #  Backend implementations                                            #
    # ------------------------------------------------------------------ #

    # ------------------------------------------------------------------ #
    #  Backend implementation                                             #
    # ------------------------------------------------------------------ #

    def generate_script(self, topic, length_seconds=45):
        """Generates script using Groq exclusively."""
        prompt = self._build_prompt(topic, length_seconds)
        print(f"Generating script via Groq for topic: '{topic}'...")

        from openai import OpenAI
        try:
            client = OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=self.groq_key,
            )
            response = client.chat.completions.create(
                model=self.groq_model,
                messages=[{"role": "user", "content": prompt}],
            )
            return self._parse_response(response.choices[0].message.content)
        except Exception as e:
            print(f"[ScriptGen] Groq Error: {e}")
            raise RuntimeError(f"Script generation failed via Groq: {e}")

if __name__ == "__main__":
    # Test execution
    try:
        generator = ScriptGenerator()
        topic = os.getenv("VIDEO_TOPIC", "creepiest ocean facts")
        script, keywords = generator.generate_script(topic)
        print("\n--- GENERATED SCRIPT ---")
        print(script)
        print("\n--- SCENES/KEYWORDS ---")
        print(keywords)
        print("------------------------\n")
    except Exception as e:
        print(f"Error: {e}")
