import os
import asyncio
import edge_tts
import json
from dotenv import load_dotenv

class AudioGenerator:
    def __init__(self):
        load_dotenv()
        self.voice = os.getenv("VOICE_NAME", "en-US-ChristopherNeural")

    async def _generate_audio_async(self, text, output_file, subtitle_file="temp_subs.json"):
        print(f"Generating audio using voice: {self.voice}...")
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                communicate = edge_tts.Communicate(text, self.voice, rate="+5%")
                subs_data = [] 
                
                with open(output_file, "wb") as file:
                    async for chunk in communicate.stream():
                        if chunk["type"] == "audio":
                            file.write(chunk["data"])
                        elif "Boundary" in chunk["type"]:
                            # Edge-TTS offset and duration are measuring in 100-nanosecond units.
                            start_sec = chunk.get("offset", 0) / 10000000.0
                            duration_sec = chunk.get("duration", 0) / 10000000.0
                            end_sec = start_sec + duration_sec
                            # Sometimes the API returns 'text' as a dict or other formats for sentences
                            text_val = chunk.get("text", "")
                            
                            subs_data.append({
                                "text": text_val,
                                "start": start_sec,
                                "end": end_sec
                            })
                            
                with open(subtitle_file, "w") as f:
                    json.dump(subs_data, f)
                    
                # Success
                return

            except Exception as e:
                print(f"[!] Network Error building TTS (Attempt {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    raise e
                print("Retrying in 2 seconds...")
                await asyncio.sleep(2)

    def generate_audio_and_subs(self, text, output_file="temp_audio.mp3", subtitle_file="temp_subs.json"):
        asyncio.run(self._generate_audio_async(text, output_file, subtitle_file))
        if os.path.exists(output_file) and os.path.exists(subtitle_file):
            print(f"Audio and Subs successfully generated!")
            return output_file, subtitle_file
        else:
            raise FileNotFoundError(f"Failed to generate {output_file} or {subtitle_file}")

if __name__ == "__main__":
    generator = AudioGenerator()
    test_text = "Did you know that water makes up over seventy percent of the human brain? Subscribe for more wild facts!"
    generator.generate_audio_and_subs(test_text, "test_audio.mp3", "test_subs.json")
