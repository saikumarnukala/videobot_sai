import os
from src.script_generator import ScriptGenerator
from dotenv import load_dotenv

def test_gemini():
    load_dotenv()
    print("Testing Gemini API...")
    try:
        gen = ScriptGenerator()
        script, keywords = gen.generate_script("test topic", length_seconds=10)
        print("Successfully generated script!")
        print(f"Script: {script[:50]}...")
    except Exception as e:
        print(f"Gemini Error: {e}")

if __name__ == "__main__":
    test_gemini()
