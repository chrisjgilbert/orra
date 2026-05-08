import os
from functools import wraps
from typing import Any, Optional

from flask import (
    Flask,
    Response,
    abort,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
    current_app,
)

from app.feed import build_feed
from app.jobs import run_audio_job, run_in_background, run_transcript_job
from app.models import (
    Episode,
    get_episode,
    init_db,
    list_episodes,
    save_episode,
)


def _build_transcript_generator() -> Any:
    """Construct the real Anthropic-backed generator from env."""
    from anthropic import Anthropic
    from app.transcript import TranscriptGenerator, DEFAULT_MODEL

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is required")
    model = os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL)
    return TranscriptGenerator(client=Anthropic(api_key=api_key), model=model)


def _build_tts_provider() -> Any:
    from app.tts import get_provider

    name = os.environ.get("TTS_PROVIDER", "openai")
    if name == "elevenlabs":
        api_key = os.environ.get("ELEVENLABS_API_KEY")
        voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
    elif name == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        voice_id = os.environ.get("OPENAI_VOICE", "alloy")
    else:
        raise ValueError(f"Unknown TTS_PROVIDER: {name}")
    if not api_key:
        raise RuntimeError(f"API key for TTS provider '{name}' is required")
    return get_provider(name, api_key=api_key, voice_id=voice_id)


def create_app(
    config: Optional[dict] = None,
    *,
    transcript_generator: Any = None,
    tts_provider: Any = None,
) -> Flask:
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "static"),
    )

    defaults = {
        "DB_PATH": os.environ.get("DB_PATH", "/data/orra.sqlite3"),
        "AUDIO_DIR": os.environ.get("AUDIO_DIR", "/data/audio"),
        "BASE_URL": os.environ.get("BASE_URL", "http://localhost:8000"),
        "FEED_TITLE": os.environ.get("FEED_TITLE", "Orra Podcast"),
        "FEED_DESCRIPTION": os.environ.get(
            "FEED_DESCRIPTION", "Auto-generated single-voice episodes"
        ),
        "FEED_AUTHOR": os.environ.get("FEED_AUTHOR", "Orra"),
        "AUTH_TOKEN": os.environ.get("AUTH_TOKEN"),
        "RUN_JOBS_INLINE": False,
    }
    if config:
        defaults.update(config)
    app.config.update(defaults)

    app.config["DB_PATH"] = os.path.abspath(app.config["DB_PATH"])
    app.config["AUDIO_DIR"] = os.path.abspath(app.config["AUDIO_DIR"])

    init_db(app.config["DB_PATH"])
    os.makedirs(app.config["AUDIO_DIR"], exist_ok=True)

    app.transcript_generator = transcript_generator
    app.tts_provider = tts_provider

    _register_routes(app)
    return app


def _get_transcript_generator() -> Any:
    if current_app.transcript_generator is None:
        current_app.transcript_generator = _build_transcript_generator()
    return current_app.transcript_generator


def _get_tts_provider() -> Any:
    if current_app.tts_provider is None:
        current_app.tts_provider = _build_tts_provider()
    return current_app.tts_provider


def _require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        token = current_app.config.get("AUTH_TOKEN")
        if not token:
            return view(*args, **kwargs)
        header = request.headers.get("Authorization", "")
        provided = header.removeprefix("Bearer ").strip()
        if provided != token:
            cookie = request.cookies.get("orra_token", "")
            if cookie != token:
                return Response("unauthorized", status=401)
        return view(*args, **kwargs)

    return wrapped


def _kick_job(target, *args, **kwargs) -> None:
    if current_app.config.get("RUN_JOBS_INLINE"):
        target(*args, **kwargs)
    else:
        run_in_background(target, *args, **kwargs)


def _register_routes(app: Flask) -> None:
    @app.get("/")
    @_require_auth
    def index():
        episodes = list_episodes(app.config["DB_PATH"], published_only=False)
        return render_template("index.html", episodes=episodes)

    @app.post("/episodes")
    @_require_auth
    def create_episode():
        prompt = request.form.get("prompt", "").strip()
        if not prompt:
            return Response("prompt is required", status=400)
        target_minutes = int(request.form.get("target_minutes", "20"))

        ep = save_episode(
            app.config["DB_PATH"],
            Episode(prompt=prompt, target_minutes=target_minutes),
        )
        _kick_job(
            run_transcript_job,
            app.config["DB_PATH"],
            ep.id,
            _get_transcript_generator(),
        )
        return redirect(url_for("show_episode", episode_id=ep.id))

    @app.get("/episodes/<int:episode_id>")
    @_require_auth
    def show_episode(episode_id: int):
        ep = get_episode(app.config["DB_PATH"], episode_id)
        if ep is None:
            abort(404)
        return render_template("episode.html", ep=ep)

    @app.post("/episodes/<int:episode_id>/edit")
    @_require_auth
    def edit_episode(episode_id: int):
        instruction = request.form.get("instruction", "").strip()
        if not instruction:
            return Response("instruction is required", status=400)
        ep = get_episode(app.config["DB_PATH"], episode_id)
        if ep is None:
            abort(404)
        if not ep.transcript:
            return Response("no transcript yet", status=400)

        gen = _get_transcript_generator()
        ep.transcript = gen.edit(transcript=ep.transcript, instruction=instruction)
        save_episode(app.config["DB_PATH"], ep)
        return redirect(url_for("show_episode", episode_id=ep.id))

    @app.post("/episodes/<int:episode_id>/publish")
    @_require_auth
    def publish_episode(episode_id: int):
        ep = get_episode(app.config["DB_PATH"], episode_id)
        if ep is None:
            abort(404)
        if not ep.transcript:
            return Response("transcript not ready", status=400)

        _kick_job(
            run_audio_job,
            app.config["DB_PATH"],
            ep.id,
            _get_tts_provider(),
            audio_dir=app.config["AUDIO_DIR"],
        )
        return redirect(url_for("show_episode", episode_id=ep.id))

    @app.get("/feed.xml")
    def feed():
        episodes = list_episodes(app.config["DB_PATH"], published_only=True)
        xml = build_feed(
            episodes=episodes,
            base_url=app.config["BASE_URL"],
            title=app.config["FEED_TITLE"],
            description=app.config["FEED_DESCRIPTION"],
            author=app.config["FEED_AUTHOR"],
        )
        return Response(xml, mimetype="application/rss+xml")

    @app.get("/audio/<path:filename>")
    def audio(filename: str):
        return send_from_directory(
            app.config["AUDIO_DIR"], filename, mimetype="audio/mpeg"
        )

    @app.get("/healthz")
    def healthz():
        return {"ok": True}
