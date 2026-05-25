"""llama-cpp-python text generation worker."""

from __future__ import annotations

from typing import Any, Callable


TokenCallback = Callable[[str], None]


class LlamaWorker:
    """Lazy wrapper around llama-cpp-python with streaming callbacks."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.model_path = config.get("model_path")
        self.n_ctx = config.get("n_ctx", 4096)
        self.max_tokens = config.get("max_tokens", 512)
        self.temperature = config.get("temperature", 0.2)
        self._llm = None

    def generate(self, prompt: str, token_callback: TokenCallback | None = None) -> str:
        llm = self._load_model()
        chunks = llm(
            prompt,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            stream=True,
        )
        answer_parts: list[str] = []
        for chunk in chunks:
            token = chunk.get("choices", [{}])[0].get("text", "")
            if not token:
                continue
            answer_parts.append(token)
            if token_callback is not None:
                token_callback(token)
        return "".join(answer_parts).strip()

    def _load_model(self):
        if self._llm is None:
            if not self.model_path:
                raise RuntimeError("Configure llm.model_path before generation")
            try:
                from llama_cpp import Llama
            except ImportError as exc:  # pragma: no cover - depends on deployment
                raise RuntimeError("Install llama-cpp-python to run local LLM generation") from exc
            self._llm = Llama(model_path=self.model_path, n_ctx=self.n_ctx)
        return self._llm

