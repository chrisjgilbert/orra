import pytest
import responses

from app.tts import get_provider, TTSError
from app.tts.elevenlabs import ElevenLabsProvider
from app.tts.openai import OpenAIProvider


def test_get_provider_returns_elevenlabs_by_default():
    p = get_provider("elevenlabs", api_key="k", voice_id="v")
    assert isinstance(p, ElevenLabsProvider)


def test_get_provider_returns_openai():
    p = get_provider("openai", api_key="k", voice_id="alloy")
    assert isinstance(p, OpenAIProvider)


def test_get_provider_unknown_raises():
    with pytest.raises(ValueError, match="Unknown TTS provider"):
        get_provider("nope", api_key="k", voice_id="v")


@responses.activate
def test_elevenlabs_synthesize_posts_text_and_returns_bytes():
    responses.add(
        responses.POST,
        "https://api.elevenlabs.io/v1/text-to-speech/voice123",
        body=b"\xff\xfb\x90\x44AUDIO",
        status=200,
        content_type="audio/mpeg",
    )

    provider = ElevenLabsProvider(api_key="secret-key", voice_id="voice123")
    audio = provider.synthesize("Hello world")

    assert audio == b"\xff\xfb\x90\x44AUDIO"
    sent = responses.calls[0].request
    assert sent.headers["xi-api-key"] == "secret-key"
    assert b"Hello world" in sent.body


@responses.activate
def test_elevenlabs_raises_on_http_error():
    responses.add(
        responses.POST,
        "https://api.elevenlabs.io/v1/text-to-speech/v",
        json={"error": "bad"},
        status=401,
    )
    provider = ElevenLabsProvider(api_key="k", voice_id="v")
    with pytest.raises(TTSError):
        provider.synthesize("hi")


@responses.activate
def test_openai_synthesize_posts_text_and_returns_bytes():
    responses.add(
        responses.POST,
        "https://api.openai.com/v1/audio/speech",
        body=b"OPENAI_AUDIO_BYTES",
        status=200,
        content_type="audio/mpeg",
    )

    provider = OpenAIProvider(api_key="sk-test", voice_id="alloy")
    audio = provider.synthesize("Hello there")

    assert audio == b"OPENAI_AUDIO_BYTES"
    sent = responses.calls[0].request
    assert sent.headers["Authorization"] == "Bearer sk-test"
    assert b"Hello there" in sent.body
    assert b"alloy" in sent.body


@responses.activate
def test_openai_raises_on_http_error():
    responses.add(
        responses.POST,
        "https://api.openai.com/v1/audio/speech",
        json={"error": "bad"},
        status=500,
    )
    provider = OpenAIProvider(api_key="k", voice_id="alloy")
    with pytest.raises(TTSError):
        provider.synthesize("hi")


def test_chunking_long_text_for_synthesis():
    """Long transcripts should be split into chunks at sentence boundaries."""
    from app.tts import chunk_text

    text = ". ".join([f"Sentence number {i}" for i in range(200)]) + "."
    chunks = chunk_text(text, max_chars=500)

    assert len(chunks) > 1
    assert all(len(c) <= 500 for c in chunks)
    # No content lost
    rejoined = " ".join(chunks)
    for i in range(200):
        assert f"Sentence number {i}" in rejoined


@responses.activate
def test_synthesize_long_concatenates_chunk_audio():
    """A provider's synthesize_long should make multiple calls and concatenate bytes."""
    responses.add(
        responses.POST,
        "https://api.openai.com/v1/audio/speech",
        body=b"AAA",
        status=200,
        content_type="audio/mpeg",
    )
    responses.add(
        responses.POST,
        "https://api.openai.com/v1/audio/speech",
        body=b"BBB",
        status=200,
        content_type="audio/mpeg",
    )

    text = ". ".join(f"Sentence {i}" for i in range(60)) + "."
    provider = OpenAIProvider(api_key="k", voice_id="alloy")
    audio = provider.synthesize_long(text, max_chars=200)

    assert audio.startswith(b"AAA") or audio.startswith(b"BBB")
    assert len(responses.calls) >= 2
