import os
import threading
from typing import Any

from app.models import (
    Episode,
    get_episode,
    save_episode,
    mark_published,
)


def _load(db_path: str, episode_id: int) -> Episode:
    ep = get_episode(db_path, episode_id)
    if ep is None:
        raise ValueError(f"Episode {episode_id} not found")
    return ep


def _mark_failed(db_path: str, episode_id: int, message: str) -> None:
    ep = get_episode(db_path, episode_id)
    if ep is None:
        return
    ep.status = "failed"
    ep.error = message
    save_episode(db_path, ep)


def run_transcript_job(db_path: str, episode_id: int, generator: Any) -> None:
    try:
        ep = _load(db_path, episode_id)
        ep.status = "generating_transcript"
        ep.error = None
        save_episode(db_path, ep)

        transcript = generator.generate(ep.prompt, target_minutes=ep.target_minutes)
        title = generator.generate_title(prompt=ep.prompt, transcript=transcript)

        ep.transcript = transcript
        ep.title = title
        ep.status = "transcript_ready"
        save_episode(db_path, ep)
    except Exception as e:
        _mark_failed(db_path, episode_id, str(e))


def _estimate_duration_seconds(text: str, words_per_minute: int = 150) -> int:
    words = len(text.split())
    return int((words / words_per_minute) * 60)


def run_audio_job(
    db_path: str,
    episode_id: int,
    provider: Any,
    *,
    audio_dir: str,
) -> None:
    try:
        ep = _load(db_path, episode_id)
        if not ep.transcript:
            raise ValueError("Cannot generate audio: no transcript")

        ep.status = "generating_audio"
        ep.error = None
        save_episode(db_path, ep)

        audio_bytes = provider.synthesize_long(ep.transcript)

        os.makedirs(audio_dir, exist_ok=True)
        filename = f"episode-{episode_id}.mp3"
        full_path = os.path.join(audio_dir, filename)
        with open(full_path, "wb") as f:
            f.write(audio_bytes)

        duration = _estimate_duration_seconds(ep.transcript)
        mark_published(db_path, episode_id, audio_path=filename, duration_seconds=duration)
    except Exception as e:
        _mark_failed(db_path, episode_id, str(e))


def run_in_background(target, *args, **kwargs) -> threading.Thread:
    """Fire-and-forget background runner. Returned thread is daemonized."""
    t = threading.Thread(target=target, args=args, kwargs=kwargs, daemon=True)
    t.start()
    return t
