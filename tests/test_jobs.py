import os
from unittest.mock import MagicMock

from app.models import Episode, init_db, save_episode, get_episode
from app.jobs import run_transcript_job, run_audio_job


def test_transcript_job_writes_transcript_and_title_and_marks_ready(tmp_db):
    init_db(tmp_db)
    ep = save_episode(tmp_db, Episode(prompt="event-driven", target_minutes=15))

    generator = MagicMock()
    generator.generate.return_value = "Welcome to today's episode about event-driven systems."
    generator.generate_title.return_value = "Why Event-Driven?"

    run_transcript_job(tmp_db, ep.id, generator)

    refreshed = get_episode(tmp_db, ep.id)
    assert refreshed.transcript == "Welcome to today's episode about event-driven systems."
    assert refreshed.title == "Why Event-Driven?"
    assert refreshed.status == "transcript_ready"
    generator.generate.assert_called_once_with("event-driven", target_minutes=15)


def test_transcript_job_marks_failed_on_exception(tmp_db):
    init_db(tmp_db)
    ep = save_episode(tmp_db, Episode(prompt="x", target_minutes=10))

    generator = MagicMock()
    generator.generate.side_effect = RuntimeError("api down")

    run_transcript_job(tmp_db, ep.id, generator)

    refreshed = get_episode(tmp_db, ep.id)
    assert refreshed.status == "failed"
    assert "api down" in refreshed.error


def test_audio_job_writes_mp3_and_marks_published(tmp_db, tmp_audio_dir):
    init_db(tmp_db)
    ep = save_episode(
        tmp_db,
        Episode(
            prompt="x",
            target_minutes=10,
            transcript="hello world.",
            status="transcript_ready",
        ),
    )

    provider = MagicMock()
    provider.synthesize_long.return_value = b"FAKEMP3DATA"

    run_audio_job(tmp_db, ep.id, provider, audio_dir=tmp_audio_dir)

    refreshed = get_episode(tmp_db, ep.id)
    assert refreshed.status == "published"
    assert refreshed.audio_path is not None
    assert refreshed.published_at is not None

    full = os.path.join(tmp_audio_dir, refreshed.audio_path)
    assert os.path.exists(full)
    with open(full, "rb") as f:
        assert f.read() == b"FAKEMP3DATA"


def test_audio_job_marks_failed_on_exception(tmp_db, tmp_audio_dir):
    init_db(tmp_db)
    ep = save_episode(
        tmp_db,
        Episode(prompt="x", target_minutes=10, transcript="hi.", status="transcript_ready"),
    )

    provider = MagicMock()
    provider.synthesize_long.side_effect = RuntimeError("tts blew up")

    run_audio_job(tmp_db, ep.id, provider, audio_dir=tmp_audio_dir)

    refreshed = get_episode(tmp_db, ep.id)
    assert refreshed.status == "failed"
    assert "tts blew up" in refreshed.error
