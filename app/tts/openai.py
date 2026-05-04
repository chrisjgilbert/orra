import requests

from app.tts.base import TTSProvider, TTSError


class OpenAIProvider(TTSProvider):
    URL = "https://api.openai.com/v1/audio/speech"
    MODEL_ID = "tts-1-hd"

    def synthesize(self, text: str) -> bytes:
        try:
            resp = requests.post(
                self.URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.MODEL_ID,
                    "voice": self.voice_id,
                    "input": text,
                    "response_format": "mp3",
                },
                timeout=300,
            )
        except requests.RequestException as e:
            raise TTSError(f"OpenAI request failed: {e}") from e

        if resp.status_code != 200:
            raise TTSError(
                f"OpenAI returned {resp.status_code}: {resp.text[:200]}"
            )
        return resp.content
