from abc import ABC, abstractmethod


class TTSError(Exception):
    pass


class TTSProvider(ABC):
    """Pluggable text-to-speech provider."""

    def __init__(self, api_key: str, voice_id: str):
        self.api_key = api_key
        self.voice_id = voice_id

    @abstractmethod
    def synthesize(self, text: str) -> bytes:
        """Return MP3 bytes for the given text."""

    def synthesize_long(self, text: str, max_chars: int = 4000) -> bytes:
        from app.tts import chunk_text

        chunks = chunk_text(text, max_chars=max_chars)
        return b"".join(self.synthesize(c) for c in chunks)
