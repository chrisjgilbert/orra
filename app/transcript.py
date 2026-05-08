import logging
import time
from typing import Any, Optional

log = logging.getLogger(__name__)

WORDS_PER_MINUTE = 150
DEFAULT_MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are a podcast scriptwriter producing a single-narrator audio script.

Rules:
- Single voice throughout. No speaker labels, no dialogue, no stage directions.
- Conversational, flowing prose suitable for being read aloud.
- Open with a strong hook in the first sentence. Close with a clear sign-off.
- No markdown, no headings, no bullet points. Plain sentences only.
- Use the web_search tool whenever the topic is time-sensitive or requires current facts.
- Never mention that you used a tool or that you are an AI.
- Aim for the requested word count plus or minus 10 percent."""

EDIT_SYSTEM_PROMPT = """You revise podcast scripts for a single narrator.

Apply the user's instruction to the transcript and return the FULL revised transcript.
Do not include any explanation, preface, or markdown — only the revised script text."""

TITLE_SYSTEM_PROMPT = """You write short, punchy podcast episode titles.
Return ONLY the title text. No quotes, no markdown, max 8 words."""


def estimate_target_words(target_minutes: int) -> int:
    return target_minutes * WORDS_PER_MINUTE


def extract_text_from_response(response: Any) -> str:
    parts = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "".join(parts)


class TranscriptGenerator:
    def __init__(self, client: Any, model: str = DEFAULT_MODEL):
        self.client = client
        self.model = model

    def _web_search_tools(self) -> list[dict]:
        return [{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}]

    def generate(self, prompt: str, target_minutes: int) -> str:
        target_words = estimate_target_words(target_minutes)
        user_msg = (
            f"Write a {target_minutes}-minute podcast script (~{target_words} words) on:\n\n"
            f"{prompt}\n\n"
            f"Use web_search for any current facts. Single narrator, plain prose."
        )
        log.info("anthropic.generate start model=%s target_minutes=%s", self.model, target_minutes)
        t0 = time.monotonic()
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=8000,
            system=SYSTEM_PROMPT,
            tools=self._web_search_tools(),
            messages=[{"role": "user", "content": user_msg}],
        )
        log.info(
            "anthropic.generate done elapsed=%.1fs stop_reason=%s usage=%s",
            time.monotonic() - t0,
            getattr(resp, "stop_reason", None),
            getattr(resp, "usage", None),
        )
        return extract_text_from_response(resp).strip()

    def edit(self, transcript: str, instruction: str) -> str:
        user_msg = (
            f"INSTRUCTION:\n{instruction}\n\n"
            f"CURRENT TRANSCRIPT:\n{transcript}"
        )
        log.info("anthropic.edit start model=%s", self.model)
        t0 = time.monotonic()
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=8000,
            system=EDIT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        log.info("anthropic.edit done elapsed=%.1fs usage=%s", time.monotonic() - t0, getattr(resp, "usage", None))
        return extract_text_from_response(resp).strip()

    def generate_title(self, prompt: str, transcript: str) -> str:
        excerpt = transcript[:1000]
        user_msg = (
            f"Topic: {prompt}\n\nOpening of the script:\n{excerpt}\n\n"
            f"Write the episode title."
        )
        log.info("anthropic.title start model=%s", self.model)
        t0 = time.monotonic()
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=60,
            system=TITLE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        log.info("anthropic.title done elapsed=%.1fs usage=%s", time.monotonic() - t0, getattr(resp, "usage", None))
        return extract_text_from_response(resp).strip().strip('"').strip("'")
