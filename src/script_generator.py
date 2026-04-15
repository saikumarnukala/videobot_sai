import os
import json
from dotenv import load_dotenv

# Quota / server errors that should trigger fallback instead of crashing
_QUOTA_SIGNALS = ["429", "503", "RESOURCE_EXHAUSTED", "overloaded", "quota",
                  "rate_limit", "rate limit", "too many requests"]

def _is_quota_error(err: str) -> bool:
    low = err.lower()
    return any(s.lower() in low for s in _QUOTA_SIGNALS)


class ScriptGenerator:
    def __init__(self):
        load_dotenv()

        # --- Gemini ---
        self.gemini_key  = os.getenv("GEMINI_API_KEY")
        self.model_name  = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.gemini_client = None
        if self.gemini_key and self.gemini_key != "your_gemini_api_key_here":
            from google import genai
            self.gemini_client = genai.Client(api_key=self.gemini_key)

        # --- GitHub Copilot (Models API) ---
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.github_model = os.getenv("GITHUB_COPILOT_MODEL", "gpt-4o")

        # --- Groq (free, 14 400 req/day) ---
        self.groq_key   = os.getenv("GROQ_API_KEY")
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

        backends = [
            self.gemini_client,
            self.github_token,
            self.groq_key,
        ]
        if not any(backends):
            raise ValueError(
                "No AI backend available. Set at least one of: "
                "GEMINI_API_KEY, GITHUB_TOKEN, GROQ_API_KEY in .env"
            )

    # ------------------------------------------------------------------ #
    #  Shared helpers                                                      #
    # ------------------------------------------------------------------ #

    def _build_prompt(self, topic, length_seconds):
        word_count = int(length_seconds) * 3
        return f"""
        You are an expert short-form video scriptwriter for YouTube Shorts and Instagram Reels.
        Write a highly engaging, fast-paced script about: {topic}.

        The script should take exactly {length_seconds} seconds to read aloud (approximately {word_count} words).

        CRITICAL RULES:
        1. Start with a massive hook to grab attention in the first 3 seconds.
        2. Keep sentences extremely short and punchy.
        3. Do NOT include any stage directions like [Hook]. ONLY the spoken words.
        4. You must ALSO generate exactly 3 background video search keywords.
           These will be searched on Pexels stock video — so they MUST be generic, visual,
           and physically filmable concepts (NOT political figures, flags, maps, or branded content).
           Good examples: "ocean waves crashing", "city skyline night", "busy stock market traders",
           "military ships at sea", "government building exterior", "crowd protest street",
           "hands shaking deal", "news anchor speaking", "courtroom interior", "fire explosion".
           Match the MOOD and THEME of the script, not the specific names or places.

        OUTPUT FORMAT: You must output ONLY a valid JSON object matching this exact structure:
        {{
            "script": "The actual full text to be spoken...",
            "keywords": ["busy stock market traders", "military ships at sea", "government building exterior"]
        }}
        """

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

    def _try_gemini(self, prompt):
        response = self.gemini_client.models.generate_content(
            model=self.model_name, contents=prompt
        )
        return self._parse_response(response.text)

    def _try_github_copilot(self, prompt):
        from openai import OpenAI
        client = OpenAI(
            base_url="https://models.inference.ai.azure.com",
            api_key=self.github_token,
        )
        response = client.chat.completions.create(
            model=self.github_model,
            messages=[{"role": "user", "content": prompt}],
        )
        return self._parse_response(response.choices[0].message.content)

    def _try_groq(self, prompt):
        from openai import OpenAI
        client = OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=self.groq_key,
        )
        response = client.chat.completions.create(
            model=self.groq_model,
            messages=[{"role": "user", "content": prompt}],
        )
        return self._parse_response(response.choices[0].message.content)

    # ------------------------------------------------------------------ #
    #  Main entry point with waterfall fallback                           #
    # ------------------------------------------------------------------ #

    def generate_script(self, topic, length_seconds=45):
        """
        Waterfall fallback order:
          1. Gemini  (paid / free tier)
          2. GitHub Copilot Models API  (150 req/day free with Copilot licence)
          3. Groq  (14 400 req/day, free, ~2 s response)
        """
        prompt = self._build_prompt(topic, length_seconds)
        print(f"Generating script & scenes for topic: '{topic}'...")

        backends = []

        if self.gemini_client:
            backends.append(("Gemini",         self._try_gemini))
        if self.github_token:
            backends.append(("GitHub Copilot", self._try_github_copilot))
        if self.groq_key:
            backends.append(("Groq",           self._try_groq))

        last_err = None
        for name, fn in backends:
            try:
                result = fn(prompt)
                if name != "Gemini":
                    print(f"[ScriptGen] [OK] Script generated via {name}")
                return result
            except Exception as e:
                err = str(e)
                if _is_quota_error(err) or name in ("GitHub Copilot", "Groq", "Ollama"):
                    print(f"[ScriptGen] {name} unavailable: {err[:100].strip()}")
                    next_idx = [n for n, _ in backends].index(name) + 1
                    if next_idx < len(backends):
                        print(f"[ScriptGen] Falling back to {backends[next_idx][0]}...")
                    last_err = e
                else:
                    raise

        raise RuntimeError(
            f"All AI backends exhausted. Last error: {last_err}\n"
            "Options: enable Gemini billing, check GITHUB_TOKEN, or check GROQ_API_KEY"
        )

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
