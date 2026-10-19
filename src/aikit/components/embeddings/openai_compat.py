from __future__ import annotations

from aikit.components._openai_http import OpenAICompatClient
from aikit.core.errors import LLMError
from aikit.core.registry import register


@register("embedder", "openai_compat")
class OpenAICompatEmbedder:
    """Embeddings from an OpenAI-compatible `/embeddings` endpoint.

    `query_prefix` and `document_prefix` support instruction-tuned models
    (for example e5 uses "query: " and "passage: ").
    """

    def __init__(
        self,
        model: str,
        base_url: str,
        api_key: str | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 60.0,
        max_retries: int = 3,
        retry_backoff: float = 0.5,
        verify: bool | str = True,
        batch_size: int = 64,
        dimensions: int | None = None,
        query_prefix: str = "",
        document_prefix: str = "",
    ) -> None:
        self.model = model
        self.batch_size = batch_size
        self.dimensions = dimensions
        self.query_prefix = query_prefix
        self.document_prefix = document_prefix
        self.http = OpenAICompatClient(
            base_url=base_url,
            api_key=api_key or None,
            headers=headers,
            timeout=timeout,
            max_retries=max_retries,
            retry_backoff=retry_backoff,
            verify=verify,
        )

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        payload: dict[str, object] = {"model": self.model, "input": texts}
        if self.dimensions:
            payload["dimensions"] = self.dimensions
        data = await self.http.post_json("/embeddings", payload)
        items = sorted(data.get("data") or [], key=lambda item: item.get("index", 0))
        if len(items) != len(texts):
            raise LLMError(f"Expected {len(texts)} embeddings, got {len(items)}")
        return [list(map(float, item["embedding"])) for item in items]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = [self.document_prefix + t for t in texts[start : start + self.batch_size]]
            vectors.extend(await self._embed_batch(batch))
        return vectors

    async def embed_query(self, text: str) -> list[float]:
        return (await self._embed_batch([self.query_prefix + text]))[0]

    async def aclose(self) -> None:
        await self.http.aclose()
