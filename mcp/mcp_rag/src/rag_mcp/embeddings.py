"""Pluggable embedding backends.

This is the primary provider-coupling point. The default (`fastembed`) runs locally with no API
key, which is what makes the server usable out of the box. To specialize, implement the small
`Embedder` protocol and register it in `get_embedder`. A hosted `GeminiEmbedder` is included as a
worked example of that swap.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from rag_mcp.config import RagConfig


@runtime_checkable
class Embedder(Protocol):
    """Minimal contract every embedding backend must satisfy."""

    name: str

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text, in order."""
        ...


class FastEmbedEmbedder:
    """Local ONNX embeddings via fastembed — no API key, no torch. The default backend."""

    def __init__(self, model: str) -> None:
        # Imported lazily so the server boots (and `--help` works) without the model downloaded.
        from fastembed import TextEmbedding

        self.name = f"fastembed:{model}"
        self._model = TextEmbedding(model_name=model)

    def embed(self, texts: list[str]) -> list[list[float]]:
        # fastembed yields numpy arrays; hand back plain lists so callers stay backend-agnostic.
        return [vector.tolist() for vector in self._model.embed(texts)]


class GeminiEmbedder:
    """Hosted embeddings via Google Generative AI. Example of a swapped-in hosted backend.

    Activated with RAG_EMBED_BACKEND=gemini and a GEMINI_API_KEY. Requires the optional
    dependency: install the package with the `gemini` extra.
    """

    def __init__(self, model: str) -> None:
        import os

        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                "RAG_EMBED_BACKEND=gemini but GEMINI_API_KEY is not set. "
                "Set the key or switch RAG_EMBED_BACKEND back to 'fastembed'."
            )
        try:
            import google.generativeai as genai
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise RuntimeError(
                "The 'gemini' backend needs google-generativeai. Install with the gemini extra, "
                "e.g. `uv pip install 'qbiz-rag-mcp[gemini]'`."
            ) from exc

        genai.configure(api_key=api_key)
        self._genai = genai
        # Gemini models are addressed as e.g. "models/text-embedding-004".
        self._model = model if model.startswith("models/") else f"models/{model}"
        self.name = f"gemini:{self._model}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        result = self._genai.embed_content(model=self._model, content=texts)
        return result["embedding"]


def get_embedder(config: RagConfig) -> Embedder:
    """Construct the embedder for the configured backend.

    Add a new backend by writing a class with the `Embedder` shape and a branch here.
    """
    backend = config.embed_backend
    if backend == "fastembed":
        return FastEmbedEmbedder(config.embed_model)
    if backend == "gemini":
        return GeminiEmbedder(config.embed_model)
    raise ValueError(
        f"Unknown RAG_EMBED_BACKEND={backend!r}. Supported: 'fastembed', 'gemini'."
    )
