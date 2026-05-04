import re

from app.tts.base import TTSProvider, TTSError
from app.tts.elevenlabs import ElevenLabsProvider
from app.tts.openai import OpenAIProvider

_REGISTRY = {
    "elevenlabs": ElevenLabsProvider,
    "openai": OpenAIProvider,
}


def get_provider(name: str, *, api_key: str, voice_id: str) -> TTSProvider:
    cls = _REGISTRY.get(name.lower())
    if cls is None:
        raise ValueError(
            f"Unknown TTS provider '{name}'. Choose from: {sorted(_REGISTRY)}"
        )
    return cls(api_key=api_key, voice_id=voice_id)


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def chunk_text(text: str, max_chars: int = 4000) -> list[str]:
    """Split text into chunks no larger than max_chars, preferring sentence boundaries."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    sentences = _SENTENCE_SPLIT.split(text)
    chunks: list[str] = []
    buf = ""
    for s in sentences:
        if not s:
            continue
        candidate = (buf + " " + s).strip() if buf else s
        if len(candidate) > max_chars and buf:
            chunks.append(buf)
            buf = s
        elif len(candidate) > max_chars:
            # Single sentence longer than max_chars: hard split.
            for i in range(0, len(s), max_chars):
                chunks.append(s[i : i + max_chars])
            buf = ""
        else:
            buf = candidate
    if buf:
        chunks.append(buf)
    return chunks


__all__ = [
    "TTSProvider",
    "TTSError",
    "get_provider",
    "chunk_text",
    "ElevenLabsProvider",
    "OpenAIProvider",
]
