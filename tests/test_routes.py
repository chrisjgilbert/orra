import os
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock

import pytest

from app.web import create_app
from app.models import Episode, init_db, save_episode, get_episode


@pytest.fixture
def app(tmp_db, tmp_audio_dir):
    init_db(tmp_db)
    transcript_gen = MagicMock()
    transcript_gen.generate.return_value = "Hello world transcript."
    transcript_gen.generate_title.return_value = "Hello Title"
    transcript_gen.edit.return_value = "Edited transcript."

    tts_provider = MagicMock()
    tts_provider.synthesize_long.return_value = b"MP3"

    app = create_app(
        config={
            "DB_PATH": tmp_db,
            "AUDIO_DIR": tmp_audio_dir,
            "BASE_URL": "https://podcast.example.com",
            "FEED_TITLE": "Test Pod",
            "FEED_DESCRIPTION": "Test feed",
            "FEED_AUTHOR": "Tester",
            "AUTH_TOKEN": "secret",
            "RUN_JOBS_INLINE": True,  # synchronous for tests
        },
        transcript_generator=transcript_gen,
        tts_provider=tts_provider,
    )
    app.config["TESTING"] = True
    app.transcript_generator = transcript_gen
    app.tts_provider = tts_provider
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def _auth(token="secret"):
    return {"Authorization": f"Bearer {token}"}


def test_index_requires_auth(client):
    resp = client.get("/")
    assert resp.status_code == 401


def test_index_renders_with_auth(client):
    resp = client.get("/", headers=_auth())
    assert resp.status_code == 200
    assert b"prompt" in resp.data.lower()


def test_create_episode_runs_transcript_job_and_redirects(client, app, tmp_db):
    resp = client.post(
        "/episodes",
        data={"prompt": "iran news", "target_minutes": "20"},
        headers=_auth(),
    )
    assert resp.status_code in (302, 303)
    # Episode persisted with transcript_ready (inline mode)
    eps = []
    from app.models import list_episodes
    eps = list_episodes(tmp_db, published_only=False)
    assert len(eps) == 1
    assert eps[0].status == "transcript_ready"
    assert eps[0].transcript == "Hello world transcript."


def test_view_episode_shows_transcript(client, tmp_db):
    ep = save_episode(
        tmp_db,
        Episode(prompt="x", target_minutes=10, transcript="ABC", status="transcript_ready"),
    )
    resp = client.get(f"/episodes/{ep.id}", headers=_auth())
    assert resp.status_code == 200
    assert b"ABC" in resp.data


def test_edit_endpoint_updates_transcript(client, tmp_db, app):
    ep = save_episode(
        tmp_db,
        Episode(prompt="x", target_minutes=10, transcript="orig", status="transcript_ready"),
    )
    resp = client.post(
        f"/episodes/{ep.id}/edit",
        data={"instruction": "make it shorter"},
        headers=_auth(),
    )
    assert resp.status_code in (200, 302, 303)
    refreshed = get_episode(tmp_db, ep.id)
    assert refreshed.transcript == "Edited transcript."
    app.transcript_generator.edit.assert_called_once()


def test_publish_endpoint_runs_audio_job(client, tmp_db, tmp_audio_dir):
    ep = save_episode(
        tmp_db,
        Episode(prompt="x", target_minutes=10, transcript="hi.", status="transcript_ready"),
    )
    resp = client.post(f"/episodes/{ep.id}/publish", headers=_auth())
    assert resp.status_code in (302, 303)
    refreshed = get_episode(tmp_db, ep.id)
    assert refreshed.status == "published"
    assert refreshed.audio_path is not None
    assert os.path.exists(os.path.join(tmp_audio_dir, refreshed.audio_path))


def test_feed_endpoint_does_not_require_auth(client, tmp_db, tmp_audio_dir):
    save_episode(
        tmp_db,
        Episode(
            prompt="x",
            target_minutes=10,
            title="Pub",
            transcript="hi",
            audio_path="ep1.mp3",
            audio_duration_seconds=120,
            status="published",
            published_at="2026-05-01T10:00:00+00:00",
        ),
    )
    resp = client.get("/feed.xml")
    assert resp.status_code == 200
    assert resp.mimetype.startswith("application/")
    root = ET.fromstring(resp.data)
    items = root.findall("./channel/item")
    assert len(items) == 1


def test_audio_serves_mp3(client, tmp_audio_dir):
    path = os.path.join(tmp_audio_dir, "ep1.mp3")
    with open(path, "wb") as f:
        f.write(b"RAWBYTES")
    resp = client.get("/audio/ep1.mp3")
    assert resp.status_code == 200
    assert resp.data == b"RAWBYTES"
