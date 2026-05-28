"""Ollama text generation worker."""

from __future__ import annotations

import json
from typing import Any, Callable
from urllib.error import URLError
from urllib.request import Request, urlopen


TokenCallback = Callable[[str], None]


class OllamaWorker:
    """Small wrapper around Ollama's local HTTP API."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.model = config.get("model", "tinyllama:latest")
        self.host = config.get("host", "http://127.0.0.1:11434")
        self.system = config.get("system")
        self.temperature = config.get("temperature", 0.2)
        self.max_tokens = config.get("max_tokens")

    def generate(self, prompt: str, token_callback: TokenCallback | None = None) -> str:
        options: dict[str, Any] = {"temperature": self.temperature}
        if self.max_tokens:
            options["num_predict"] = self.max_tokens

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": options,
        }
        if self.system:
            payload["system"] = self.system
        request = Request(
            f"{self.host.rstrip('/')}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=120) as response:
                body = json.loads(response.read().decode("utf-8"))
        except URLError as exc:
            raise RuntimeError(
                "Ollama is not reachable. Start Ollama and verify `ollama list` works."
            ) from exc

        if "error" in body:
            raise RuntimeError(f"Ollama generation failed: {body['error']}")

        answer = str(body.get("response", "")).strip()
        if token_callback is not None and answer:
            token_callback(answer)
        return answer
