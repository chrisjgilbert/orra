import xml.etree.ElementTree as ET

from app.feed import build_feed
from app.models import Episode


def _published(prompt="Test", title="Test Episode", audio_path="ep1.mp3"):
    return Episode(
        id=1,
        prompt=prompt,
        target_minutes=20,
        title=title,
        transcript="full transcript here",
        audio_path=audio_path,
        audio_duration_seconds=1234,
        status="published",
        created_at="2026-05-01T10:00:00+00:00",
        published_at="2026-05-01T10:30:00+00:00",
    )


def test_build_feed_returns_valid_xml_with_channel():
    xml = build_feed(
        episodes=[_published()],
        base_url="https://podcast.example.com",
        title="My Podcast",
        description="Daily auto-generated episodes",
        author="Chris",
    )
    root = ET.fromstring(xml)
    assert root.tag == "rss"
    assert root.attrib["version"] == "2.0"
    channel = root.find("channel")
    assert channel.find("title").text == "My Podcast"
    assert channel.find("description").text == "Daily auto-generated episodes"
    assert channel.find("link").text == "https://podcast.example.com"


def test_build_feed_includes_published_episode_as_item():
    xml = build_feed(
        episodes=[_published(title="Episode One", audio_path="ep1.mp3")],
        base_url="https://p.example.com",
        title="My Podcast",
        description="d",
        author="a",
    )
    root = ET.fromstring(xml)
    items = root.findall("./channel/item")
    assert len(items) == 1
    item = items[0]
    assert item.find("title").text == "Episode One"
    enclosure = item.find("enclosure")
    assert enclosure is not None
    assert enclosure.attrib["url"] == "https://p.example.com/audio/ep1.mp3"
    assert enclosure.attrib["type"] == "audio/mpeg"


def test_build_feed_skips_unpublished_episodes():
    draft = Episode(id=2, prompt="x", target_minutes=10, status="draft")
    xml = build_feed(
        episodes=[draft, _published()],
        base_url="https://p.example.com",
        title="t",
        description="d",
        author="a",
    )
    root = ET.fromstring(xml)
    items = root.findall("./channel/item")
    assert len(items) == 1


def test_build_feed_includes_itunes_namespace_and_duration():
    xml = build_feed(
        episodes=[_published()],
        base_url="https://p.example.com",
        title="t",
        description="d",
        author="a",
    )
    assert "xmlns:itunes" in xml
    # duration 1234s → 20:34
    assert "20:34" in xml
