import os
import json
from dotenv import load_dotenv

class ScriptGenerator:
    def __init__(self):
        load_dotenv()

        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.model_name = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')

        self.github_token = os.getenv("GITHUB_TOKEN")
        self.github_model = os.getenv('GITHUB_COPILOT_MODEL', 'gpt-4o')

        # Init Gemini client only if key is present and not placeholder
        self.gemini_client = None
        if self.gemini_key and self.gemini_key != "your_gemini_api_key_here":
            from google import genai
            self.gemini_client = genai.Client(api_key=self.gemini_key)

        if not self.gemini_client and not self.github_token:
            raise ValueError(
                "No AI backend available. Set GEMINI_API_KEY or GITHUB_TOKEN in .env"
            )

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
        4. You must ALSO generate exactly 3 chronological, visually distinct search keywords matching the script's scenes. We will use these to download background stock videos.

        OUTPUT FORMAT: You must output ONLY a valid JSON object matching this exact structure:
        {{
            "script": "The actual full text to be spoken...",
            "keywords": ["mountain climbing", "dark skies abstract", "sunrise motivation"]
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

    def generate_script(self, topic, length_seconds=45):
        """
        Generates a video script based on the topic.
        Tries Gemini first; falls back to GitHub Copilot (Models API) on quota/server errors.
        """
        prompt = self._build_prompt(topic, length_seconds)
        print(f"Generating script & scenes for topic: '{topic}'...")

        if self.gemini_client:
            try:
                return self._try_gemini(prompt)
            except Exception as e:
                err = str(e)
                if any(x in err for x in ["429", "503", "RESOURCE_EXHAUSTED", "overloaded", "quota"]):
                    print(f"[ScriptGen] Gemini unavailable ({err[:80].strip()})")
                    print("[ScriptGen] Falling back to GitHub Copilot...")
                else:
                    raise

        if self.github_token:
            return self._try_github_copilot(prompt)

        raise RuntimeError(
            "All AI backends failed. Enable Gemini billing or add GITHUB_TOKEN to .env"
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
