# Orra

Personal podcast / audio narration tool. Flask app that turns a prompt into a single-voice episode: Claude writes the transcript, a TTS provider (ElevenLabs or OpenAI) renders the audio, and an RSS feed is served at `/feed.xml`.

## Requirements

- Python 3.11+
- An `ANTHROPIC_API_KEY`
- One TTS provider key:
  - `ELEVENLABS_API_KEY` (default), or
  - `OPENAI_API_KEY` with `TTS_PROVIDER=openai`

## Configuration

`wsgi.py` loads a `.env` file at startup. Example:

```env
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-opus-4-7         # optional

TTS_PROVIDER=elevenlabs                 # or "openai"
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=JBFqnCBsd6RMkjVDRZzb # optional

DB_PATH=./data/orra.sqlite3
AUDIO_DIR=./data/audio
BASE_URL=http://localhost:8000

FEED_TITLE=Orra Podcast
FEED_DESCRIPTION=Auto-generated single-voice episodes
FEED_AUTHOR=Orra

AUTH_TOKEN=                             # optional; if set, gates the UI
```

The defaults for `DB_PATH` and `AUDIO_DIR` point at `/data/...` (intended for the Docker image). Override them locally or the app won't be able to write.

## Run locally

```bash
pip install -e ".[dev]"
mkdir -p data/audio
flask --app wsgi:app run --debug --port 8000
```

Or with gunicorn (matches production):

```bash
gunicorn -w 1 --threads 4 -t 600 -b 0.0.0.0:8000 wsgi:app
```

Open http://localhost:8000.

## Run in Docker

```bash
docker build -t orra .
docker run --rm -p 8000:8000 \
  -e ANTHROPIC_API_KEY=... \
  -e ELEVENLABS_API_KEY=... \
  -v "$PWD/data:/data" \
  orra
```

The image runs gunicorn with a single worker and a 10-minute timeout, since TTS calls can take a while.

## Endpoints

- `GET  /` — episode list and create form
- `POST /episodes` — kicks off a transcript job for a prompt
- `GET  /episodes/<id>` — episode detail
- `POST /episodes/<id>/edit` — apply an editing instruction to the transcript
- `POST /episodes/<id>/publish` — render audio and publish to the feed
- `GET  /feed.xml` — podcast RSS feed
- `GET  /audio/<filename>` — published audio files
- `GET  /healthz` — health check

If `AUTH_TOKEN` is set, all UI/episode routes require either an `Authorization: Bearer <token>` header or an `orra_token` cookie. `/feed.xml`, `/audio/...`, and `/healthz` are always public.

## Tests

```bash
pytest
```
