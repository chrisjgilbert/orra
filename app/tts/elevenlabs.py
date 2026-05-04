import requests

from app.tts.base import TTSProvider, TTSError


class ElevenLabsProvider(TTSProvider):
    BASE_URL = "https://api.elevenlabs.io/v1/text-to-speech"
    MODEL_ID = "eleven_turbo_v2_5"

    def synthesize(self, text: str) -> bytes:
        url = f"{self.BASE_URL}/{self.voice_id}"
        try:
            resp = requests.post(
                url,
                headers={
                    "xi-api-key": self.api_key,
                    "accept": "audio/mpeg",
                    "content-type": "application/json",
                },
                json={
                    "text": text,
                    "model_id": self.MODEL_ID,
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
                },
                timeout=300,
            )
        except requests.RequestException as e:
            raise TTSError(f"ElevenLabs request failed: {e}") from e

        if resp.status_code != 200:
            raise TTSError(
                f"ElevenLabs returned {resp.status_code}: {resp.text[:200]}"
            )
        return resp.content
