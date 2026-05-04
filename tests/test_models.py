from app.models import Episode, init_db, save_episode, get_episode, list_episodes


def test_init_db_creates_tables(tmp_db):
    init_db(tmp_db)
    # idempotent
    init_db(tmp_db)


def test_save_and_get_episode(tmp_db):
    init_db(tmp_db)
    ep = Episode(prompt="why event-driven?", target_minutes=20)
    saved = save_episode(tmp_db, ep)
    assert saved.id is not None
    assert saved.status == "draft"
    assert saved.created_at is not None

    fetched = get_episode(tmp_db, saved.id)
    assert fetched.id == saved.id
    assert fetched.prompt == "why event-driven?"
    assert fetched.target_minutes == 20


def test_save_updates_existing_episode(tmp_db):
    init_db(tmp_db)
    ep = save_episode(tmp_db, Episode(prompt="iran news", target_minutes=10))
    ep.transcript = "Today on the news..."
    ep.status = "transcript_ready"
    save_episode(tmp_db, ep)

    fetched = get_episode(tmp_db, ep.id)
    assert fetched.transcript == "Today on the news..."
    assert fetched.status == "transcript_ready"


def test_list_episodes_returns_published_only_by_default(tmp_db):
    init_db(tmp_db)
    draft = save_episode(tmp_db, Episode(prompt="a", target_minutes=10))
    published = save_episode(
        tmp_db,
        Episode(prompt="b", target_minutes=10, status="published", audio_path="/x.mp3"),
    )

    published_only = list_episodes(tmp_db, published_only=True)
    assert [e.id for e in published_only] == [published.id]

    everything = list_episodes(tmp_db, published_only=False)
    assert {e.id for e in everything} == {draft.id, published.id}


def test_get_returns_none_for_missing(tmp_db):
    init_db(tmp_db)
    assert get_episode(tmp_db, 999) is None
