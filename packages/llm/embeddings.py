from functools import lru_cache

import numpy as np

from packages.config import get_settings


class EmbeddingService:
    DIMENSION = 384

    def __init__(self):
        self.settings = get_settings()
        self._model = None
        self._azure_client = None

    def _get_local_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.settings.embedding_model)
        return self._model

    def _get_azure_client(self):
        if self._azure_client is None and self.settings.azure_openai_api_key:
            from openai import AsyncAzureOpenAI

            self._azure_client = AsyncAzureOpenAI(
                azure_endpoint=self.settings.azure_openai_endpoint,
                api_key=self.settings.azure_openai_api_key,
                api_version="2024-02-01",
            )
        return self._azure_client

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        # Fast deterministic vectors for heuristic/offline demos (no model download).
        if self.settings.llm_provider.lower() == "heuristic":
            return [self._hash_embed(t) for t in texts]
        client = self._get_azure_client()
        if client and self.settings.azure_openai_embedding_deployment:
            resp = await client.embeddings.create(
                model=self.settings.azure_openai_embedding_deployment,
                input=texts,
            )
            vectors = [d.embedding for d in resp.data]
            if len(vectors[0]) != self.DIMENSION:
                return [self._resize(v) for v in vectors]
            return vectors
        try:
            model = self._get_local_model()
            arr = model.encode(texts, normalize_embeddings=True)
            return [self._resize(v.tolist()) for v in arr]
        except Exception:
            return [self._hash_embed(t) for t in texts]

    def _hash_embed(self, text: str) -> list[float]:
        import hashlib
        import math

        vec = [0.0] * self.DIMENSION
        tokens = text.lower().split()
        if not tokens:
            tokens = ["empty"]
        for tok in tokens:
            digest = hashlib.sha256(tok.encode("utf-8")).digest()
            for i in range(0, min(len(digest), 32)):
                idx = (digest[i] + i * 17) % self.DIMENSION
                sign = 1.0 if digest[i] % 2 == 0 else -1.0
                vec[idx] += sign
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    def _resize(self, vector: list[float]) -> list[float]:
        if len(vector) == self.DIMENSION:
            return vector
        arr = np.array(vector, dtype=np.float32)
        if len(arr) > self.DIMENSION:
            arr = arr[: self.DIMENSION]
        else:
            arr = np.pad(arr, (0, self.DIMENSION - len(arr)))
        norm = np.linalg.norm(arr)
        if norm > 0:
            arr = arr / norm
        return arr.tolist()


@lru_cache
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()
