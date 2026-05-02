# Faceless VideoBot

Fully automated Python pipeline that generates and publishes **faceless YouTube Shorts** daily — AI scripts, stock footage, TTS voiceover, dynamic subtitles, and royalty-free music. Runs locally or via **GitHub Actions** on a schedule.

## Features

- **AI Script Generation** — Groq (Llama 3.3 70B) writes viral-optimized scripts with 8 cinematic scene descriptions
- **Text-to-Speech Voiceover** — Microsoft Edge TTS with word-level subtitle timestamps
- **Stock Background Videos** — Pexels API downloads scene-matched clips per script keyword
- **Dynamic Subtitles** — Bold captions synced to audio with system font fallbacks for CI
- **Background Music** — Jamendo API auto-downloads royalty-free CC-licensed music matched to topic mood
- **Ken Burns Effect** — Optional cinematic zoom/pan on clips (disable in CI for speed)
- **Auto YouTube Upload** — YouTube Data API v3 publishes directly to your channel
- **Topic Rotation** — Never-repeat system tracks used topics in `used_topics.json`
- **Breaking News Mode** — Fetches headlines from RSS feeds and generates news videos
- **GitHub Actions CI/CD** — Automated daily pipeline with optimized rendering

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/saikumarnukala/videobot_sai.git
cd videobot_sai
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux
pip install -r requirements.txt
```

### 2. Configure API keys

```bash
cp .env.example .env         # then edit .env with your keys
```

| Key | Where to Get | Required |
|-----|-------------|----------|
| `GROQ_API_KEY` | [Groq Console](https://console.groq.com/) — Free | Yes |
| `PEXELS_API_KEY` | [Pexels API](https://www.pexels.com/api/) — Free | Yes |
| `JAMENDO_CLIENT_ID` | [Jamendo Developer](https://developer.jamendo.com/) — Free | Yes |
| `client_secrets.json` | [Google Cloud Console](https://console.cloud.google.com/) — YouTube Data API v3 | For upload |

### 3. YouTube authentication (first time only)

```bash
python src/youtube_uploader.py
```

A browser opens to authorize YouTube access. This creates `token.json` which is reused for all future runs.

### 4. Run the pipeline

```bash
# Auto-select topic based on time slot
python main.py

# Specific topic
python main.py --topic "psychology tricks that actually work"

# Breaking news mode
python main.py --news --news-index 0
```

## GitHub Actions (Automated Daily Pipeline)

The workflow runs **twice daily** at peak YouTube engagement times:

| Time (IST) | UTC | Content |
|---|---|---|
| 7:30 AM | 02:00 | Breaking news video |
| 8:30 PM | 15:00 | Topic-based video |

### Required GitHub Secrets

Go to **Settings > Secrets and variables > Actions** and add:

| Secret | Description |
|--------|-------------|
| `GROQ_API_KEY` | Groq API key |
| `PEXELS_API_KEY` | Pexels API key |
| `JAMENDO_CLIENT_ID` | Jamendo client ID |
| `YOUTUBE_CLIENT_SECRETS_JSON` | Full contents of `client_secrets.json` |
| `YOUTUBE_TOKEN_JSON` | Full contents of `token.json` |

Optional: `YOUTUBE_PRIVACY`, `GROQ_MODEL`, `EDGE_VOICE`

### Manual trigger

Go to **Actions > Daily Faceless Video Bot > Run workflow** — you can override the topic or time slot.

## Project Structure

```
videobot_sai/
├── main.py                  # Main orchestrator
├── select_topic.py          # Topic rotation with slot detection
├── topics.json              # Topic pool (morning / afternoon / evening)
├── used_topics.json         # Never-repeat ledger (auto-updated)
├── requirements.txt
├── .env.example             # API key template
├── .github/
│   └── workflows/
│       └── daily_video.yml  # GitHub Actions pipeline
└── src/
    ├── script_generator.py  # Groq AI script generation
    ├── create_audio.py      # Edge TTS voiceover + subtitle timestamps
    ├── media_fetcher.py     # Pexels stock video downloader
    ├── music_fetcher.py     # Jamendo background music (with fallback search)
    ├── news_fetcher.py      # RSS news headline fetcher
    ├── build_video.py       # MoviePy video assembly + Ken Burns effect
    └── youtube_uploader.py  # YouTube Data API v3 uploader
```

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model for script generation |
| `VIDEO_LENGTH_SECONDS` | `45` | Target video length in seconds |
| `EDGE_VOICE` | `ko-KR-HyunsuMultilingualNeural` | Edge TTS voice |
| `VOLUME_BOOST` | `+50%` | Voiceover volume boost |
| `UPLOAD_TO_YOUTUBE` | `False` | Enable YouTube upload |
| `YOUTUBE_PRIVACY` | `public` | `public`, `private`, or `unlisted` |
| `RENDER_PRESET` | `medium` | FFmpeg preset (`ultrafast` for CI) |
| `ENABLE_KEN_BURNS` | `true` | Ken Burns zoom/pan effect (`false` for faster CI renders) |
| `BGM_VOLUME` | `0.08` | Background music volume (0.0–1.0) |

## Security

Never commit `.env`, `client_secrets.json`, or `token.json`. All are listed in `.gitignore`.

## License

[MIT](LICENSE) — Sai Kumar Nukala
