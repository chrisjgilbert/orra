from datetime import datetime
from email.utils import format_datetime
from xml.sax.saxutils import escape
from typing import Iterable

from app.models import Episode

ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"


def _format_pubdate(iso_ts: str | None) -> str:
    if not iso_ts:
        return ""
    dt = datetime.fromisoformat(iso_ts)
    return format_datetime(dt)


def _format_duration(seconds: int | None) -> str:
    if not seconds:
        return "00:00"
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def build_feed(
    *,
    episodes: Iterable[Episode],
    base_url: str,
    title: str,
    description: str,
    author: str,
) -> str:
    base_url = base_url.rstrip("/")
    items_xml = []
    for ep in episodes:
        if ep.status != "published" or not ep.audio_path:
            continue
        audio_url = f"{base_url}/audio/{ep.audio_path}"
        items_xml.append(
            f"""    <item>
      <title>{escape(ep.title or ep.prompt)}</title>
      <description>{escape(ep.prompt)}</description>
      <pubDate>{_format_pubdate(ep.published_at)}</pubDate>
      <guid isPermaLink="false">orra-episode-{ep.id}</guid>
      <enclosure url="{escape(audio_url)}" type="audio/mpeg" length="0"/>
      <itunes:duration>{_format_duration(ep.audio_duration_seconds)}</itunes:duration>
    </item>"""
        )

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="{ITUNES_NS}">
  <channel>
    <title>{escape(title)}</title>
    <link>{escape(base_url)}</link>
    <description>{escape(description)}</description>
    <language>en-us</language>
    <itunes:author>{escape(author)}</itunes:author>
    <itunes:explicit>no</itunes:explicit>
{chr(10).join(items_xml)}
  </channel>
</rss>
"""
