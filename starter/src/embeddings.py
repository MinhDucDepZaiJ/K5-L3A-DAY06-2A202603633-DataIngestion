"""Real local SentenceTransformers embeddings; never mock or silently fall back."""
import math

class MyEmbedder:
    def __init__(self, model_name: str = 'sentence-transformers/all-MiniLM-L6-v2') -> None:
        from sentence_transformers import SentenceTransformer
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.dimensions = int(self.model.get_sentence_embedding_dimension())

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self.model.encode(texts, batch_size=16, normalize_embeddings=True, show_progress_bar=True)
        return [v.tolist() for v in vectors]

    def embed_query(self, question: str) -> list[float]:
        return self.model.encode([question], normalize_embeddings=True)[0].tolist()
