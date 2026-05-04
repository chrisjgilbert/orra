import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Episode:
    prompt: str
    target_minutes: int = 20
    id: Optional[int] = None
    title: Optional[str] = None
    transcript: Optional[str] = None
    audio_path: Optional[str] = None
    audio_duration_seconds: Optional[int] = None
    status: str = "draft"
    error: Optional[str] = None
    created_at: Optional[str] = None
    published_at: Optional[str] = None


SCHEMA = """
CREATE TABLE IF NOT EXISTS episodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt TEXT NOT NULL,
    target_minutes INTEGER NOT NULL DEFAULT 20,
    title TEXT,
    transcript TEXT,
    audio_path TEXT,
    audio_duration_seconds INTEGER,
    status TEXT NOT NULL DEFAULT 'draft',
    error TEXT,
    created_at TEXT NOT NULL,
    published_at TEXT
);
"""


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str) -> None:
    with _connect(db_path) as conn:
        conn.executescript(SCHEMA)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_episode(row: sqlite3.Row) -> Episode:
    return Episode(
        id=row["id"],
        prompt=row["prompt"],
        target_minutes=row["target_minutes"],
        title=row["title"],
        transcript=row["transcript"],
        audio_path=row["audio_path"],
        audio_duration_seconds=row["audio_duration_seconds"],
        status=row["status"],
        error=row["error"],
        created_at=row["created_at"],
        published_at=row["published_at"],
    )


def save_episode(db_path: str, episode: Episode) -> Episode:
    with _connect(db_path) as conn:
        if episode.id is None:
            episode.created_at = episode.created_at or _now()
            cur = conn.execute(
                """
                INSERT INTO episodes
                  (prompt, target_minutes, title, transcript, audio_path,
                   audio_duration_seconds, status, error, created_at, published_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    episode.prompt,
                    episode.target_minutes,
                    episode.title,
                    episode.transcript,
                    episode.audio_path,
                    episode.audio_duration_seconds,
                    episode.status,
                    episode.error,
                    episode.created_at,
                    episode.published_at,
                ),
            )
            episode.id = cur.lastrowid
        else:
            conn.execute(
                """
                UPDATE episodes SET
                  prompt=?, target_minutes=?, title=?, transcript=?, audio_path=?,
                  audio_duration_seconds=?, status=?, error=?, published_at=?
                WHERE id=?
                """,
                (
                    episode.prompt,
                    episode.target_minutes,
                    episode.title,
                    episode.transcript,
                    episode.audio_path,
                    episode.audio_duration_seconds,
                    episode.status,
                    episode.error,
                    episode.published_at,
                    episode.id,
                ),
            )
    return episode


def get_episode(db_path: str, episode_id: int) -> Optional[Episode]:
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM episodes WHERE id = ?", (episode_id,)
        ).fetchone()
        return _row_to_episode(row) if row else None


def list_episodes(db_path: str, *, published_only: bool = False) -> list[Episode]:
    with _connect(db_path) as conn:
        if published_only:
            sql = "SELECT * FROM episodes WHERE status = 'published' ORDER BY published_at DESC"
        else:
            sql = "SELECT * FROM episodes ORDER BY created_at DESC"
        return [_row_to_episode(r) for r in conn.execute(sql).fetchall()]


def mark_published(db_path: str, episode_id: int, audio_path: str, duration_seconds: int) -> Episode:
    ep = get_episode(db_path, episode_id)
    if ep is None:
        raise ValueError(f"Episode {episode_id} not found")
    ep.audio_path = audio_path
    ep.audio_duration_seconds = duration_seconds
    ep.status = "published"
    ep.published_at = _now()
    return save_episode(db_path, ep)
