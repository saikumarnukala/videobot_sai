import os
import asyncio
import edge_tts
from dotenv import load_dotenv

class AudioGenerator:
    def __init__(self):
        load_dotenv()
        self.voice = os.getenv("VOICE_NAME", "en-US-AndrewNeural")

    async def _generate_audio_async(self, text, output_file):
        print(f"Generating audio using voice: {self.voice}...")
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                communicate = edge_tts.Communicate(text, self.voice, rate="-15%")
                
                with open(output_file, "wb") as file:
                    async for chunk in communicate.stream():
                        if chunk["type"] == "audio":
                            file.write(chunk["data"])

                # Success
                return

            except Exception as e:
                print(f"[!] Network Error building TTS (Attempt {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    raise e
                print("Retrying in 2 seconds...")
                await asyncio.sleep(2)

    def generate_audio(self, text, output_file="temp_audio.mp3"):
        # Priority 1 – ElevenLabs paid voice clone (best quality)
        if os.getenv("ELEVENLABS_API_KEY"):
            from src.elevenlabs_audio import ElevenLabsAudioGenerator
            gen = ElevenLabsAudioGenerator()
            return gen.generate_audio(text, output_file)

        # Priority 2 – Edge TTS (free, human-sounding neural voice, no local model needed)
        asyncio.run(self._generate_audio_async(text, output_file))
        if os.path.exists(output_file):
            print(f"Audio successfully generated!")
            return output_file
        else:
            raise FileNotFoundError(f"Failed to generate {output_file}")

if __name__ == "__main__":
    generator = AudioGenerator()
    test_text = "Did you know that water makes up over seventy percent of the human brain? Subscribe for more wild facts!"
    generator.generate_audio(test_text, "test_audio.mp3")
