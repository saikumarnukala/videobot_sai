# 🎬 Faceless VideoBot

An end-to-end Python automation pipeline that generates **daily faceless YouTube Shorts** using AI, stock footage, text-to-speech, and background music — all completely free.

## 🚀 Features
- **AI Script Generation** — Google Gemini writes an engaging, punchy script based on your topic
- **Text-to-Speech Voiceover** — Microsoft Edge-TTS synthesizes a natural-sounding voice
- **Situational Background Videos** — Pexels API downloads 3 unique scene-matched stock clips
- **Dynamic Subtitles** — Bold Impact-font captions perfectly synced to the audio
- **Background Music** — Jamendo API auto-downloads royalty-free music matched to the mood
- **Auto YouTube Upload** — YouTube Data API v3 publishes directly to your channel

## 🛠 Setup

### 1. Clone the repo
```bash
git clone https://github.com/saikumarnukala/videobot_sai.git
cd videobot_sai
```

### 2. Create a virtual environment
```bash
python -m venv venv
venv\Scripts\activate   # Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure API keys
Copy `.env.example` to `.env` and fill in your keys:
```bash
copy .env.example .env
```

| Key | Where to Get |
|-----|-------------|
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/app/apikey) — Free |
| `PEXELS_API_KEY` | [Pexels API](https://www.pexels.com/api/) — Free |
| `JAMENDO_CLIENT_ID` | [Jamendo Developer](https://developer.jamendo.com/) — Free |
| `JAMENDO_ALLOWED_TRACK_IDS` | Optional comma-separated Jamendo track IDs. If set, only these approved tracks are used. |
| YouTube OAuth | Download `client_secrets.json` from [Google Cloud Console](https://console.cloud.google.com/) |

### 5. Run the pipeline
```bash
python main.py
```

The first time you run with `UPLOAD_TO_YOUTUBE=True`, a browser will open asking you to authorize YouTube. After that, it runs fully automatically every day!

## 📁 Project Structure
```
faceless/
├── main.py                  # Main orchestrator
├── requirements.txt
├── .env.example             # API key template (copy to .env)
├── client_secrets.json      # YouTube OAuth (download from GCP - NOT committed)
└── src/
    ├── script_generator.py  # Gemini AI script generation
    ├── create_audio.py      # Edge-TTS voiceover + subtitle timestamps
    ├── media_fetcher.py     # Pexels stock video downloader
    ├── music_fetcher.py     # Jamendo background music downloader
    ├── build_video.py       # MoviePy video assembly
    └── youtube_uploader.py  # YouTube Data API uploader
```

## ⚙️ Configuration (`.env`)
| Setting | Description |
|---------|-------------|
| `VIDEO_TOPIC` | The theme/niche for the video |
| `VIDEO_LENGTH_SECONDS` | Target length (default: 45s) |
| `VOICE_NAME` | Edge-TTS voice (default: `en-US-ChristopherNeural`) |
| `UPLOAD_TO_YOUTUBE` | `True` to publish, `False` to preview locally |
| `BGM_VOLUME` | Background music volume (0.0–1.0, default: 0.08) |
| `YOUTUBE_PRIVACY_STATUS` | `public`, `private`, or `unlisted` |

## 🔒 Security Note
Never commit your `.env` or `client_secrets.json`. They are listed in `.gitignore`.
