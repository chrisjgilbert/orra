from unittest.mock import MagicMock

import pytest

from app.transcript import (
    TranscriptGenerator,
    extract_text_from_response,
    estimate_target_words,
)


def _fake_response(text: str):
    """Mimic an Anthropic SDK response with a single text block."""
    block = MagicMock()
    block.type = "text"
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    return resp


def test_estimate_target_words_uses_150_wpm():
    # 20 minutes * 150 wpm = 3000 words
    assert estimate_target_words(20) == 3000
    assert estimate_target_words(10) == 1500


def test_extract_text_concatenates_text_blocks():
    block1 = MagicMock(type="text", text="Hello, ")
    block2 = MagicMock(type="text", text="world.")
    block3 = MagicMock(type="tool_use")  # ignored
    resp = MagicMock(content=[block1, block2, block3])

    assert extract_text_from_response(resp) == "Hello, world."


def test_generate_transcript_calls_claude_with_web_search_tool():
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _fake_response(
        "Welcome to today's episode about Iran..."
    )
    gen = TranscriptGenerator(client=fake_client, model="claude-sonnet-4-6")

    transcript = gen.generate("latest Iran war news", target_minutes=20)

    assert "Iran" in transcript
    fake_client.messages.create.assert_called_once()
    kwargs = fake_client.messages.create.call_args.kwargs

    # Web search tool must be wired in for grounded output
    tool_types = [t.get("type") for t in kwargs["tools"]]
    assert any("web_search" in t for t in tool_types if t)

    # Target length should be in the prompt
    user_msg = kwargs["messages"][0]["content"]
    assert "3000" in user_msg or "20" in user_msg
    assert "latest Iran war news" in user_msg

    # Single-narrator instruction in system prompt
    assert "narrator" in kwargs["system"].lower() or "single voice" in kwargs["system"].lower()


def test_generate_returns_text_stripped():
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _fake_response("  hello  ")
    gen = TranscriptGenerator(client=fake_client)
    assert gen.generate("x", target_minutes=10) == "hello"


def test_edit_transcript_passes_existing_text_and_instruction():
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _fake_response("Edited transcript here.")
    gen = TranscriptGenerator(client=fake_client)

    edited = gen.edit(
        transcript="Original transcript text.",
        instruction="Make the intro more punchy",
    )

    assert edited == "Edited transcript here."
    kwargs = fake_client.messages.create.call_args.kwargs
    user_msg = kwargs["messages"][0]["content"]
    assert "Original transcript text." in user_msg
    assert "Make the intro more punchy" in user_msg


def test_generate_title_returns_short_title():
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _fake_response("Iran's Latest Crisis Explained")
    gen = TranscriptGenerator(client=fake_client)

    title = gen.generate_title(prompt="iran war", transcript="long body...")
    assert title == "Iran's Latest Crisis Explained"
