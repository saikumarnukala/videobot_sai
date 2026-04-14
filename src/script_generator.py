import os
import json
from google import genai
from dotenv import load_dotenv

class ScriptGenerator:
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        # Configure Gemini
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key or self.api_key == "your_gemini_api_key_here":
            raise ValueError("GEMINI_API_KEY is missing or not configured in .env file.")
        
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')

    def generate_script(self, topic, length_seconds=45):
        """
        Generates a video script based on the topic.
        We estimate about 2.5 - 3 words per second for a comfortable reading pace.
        """
        word_count = int(length_seconds) * 3
        
        prompt = f"""
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
        
        print(f"Generating script & scenes for topic: '{topic}'...")
        response = self.client.models.generate_content(model=self.model_name, contents=prompt)
        
        text = response.text.strip()
        # Clean up possible markdown code blocks from Gemini
        if text.startswith("```json"):
            text = text[7:-3]
        elif text.startswith("```"):
            text = text[3:-3]
        
        # Parse the JSON response
        try:
            data = json.loads(text.strip())
            return data["script"], data["keywords"]
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON from AI: {text}")
            raise e

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
