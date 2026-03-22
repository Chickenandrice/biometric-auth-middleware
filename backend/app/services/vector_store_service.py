import chromadb
from chromadb.config import Settings as ChromaSettings

from backend.app.config import settings


class VectorStoreService:
    """Manages ECG template embeddings in ChromaDB."""

    def __init__(self):
        self._client = chromadb.Client(ChromaSettings(
            persist_directory=settings.chroma_persist_dir,
            anonymized_telemetry=False,
            is_persistent=True,
        ))
        self._collection = self._client.get_or_create_collection(
            name="ecg_templates",
            metadata={"hnsw:space": "cosine"},
        )

    def store_embedding(self, user_id: str, embedding: list[float], metadata: dict | None = None):
        """Store or update an enrollment embedding for a user."""
        meta = metadata or {}
        meta["user_id"] = user_id
        self._collection.upsert(
            ids=[user_id],
            embeddings=[embedding],
            metadatas=[meta],
        )

    def get_embedding(self, user_id: str) -> list[float] | None:
        """Retrieve the enrolled embedding for a user."""
        results = self._collection.get(ids=[user_id], include=["embeddings"])
        embeddings = results["embeddings"]
        if embeddings is not None and len(embeddings) > 0:
            return list(embeddings[0])
        return None

    def reset(self):
        """Delete all embeddings. Used for test isolation."""
        self._client.delete_collection("ecg_templates")
        self._collection = self._client.get_or_create_collection(
            name="ecg_templates",
            metadata={"hnsw:space": "cosine"},
        )

    def delete_embedding(self, user_id: str):
        """Remove a user's enrollment embedding."""
        self._collection.delete(ids=[user_id])

    def query_similar(self, embedding: list[float], n_results: int = 1) -> list[dict]:
        """Query for the most similar enrolled embeddings."""
        results = self._collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
            include=["embeddings", "metadatas", "distances"],
        )
        output = []
        for i in range(len(results["ids"][0])):
            output.append({
                "user_id": results["ids"][0][i],
                "distance": results["distances"][0][i],
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
            })
        return output


# Singleton instance
vector_store = VectorStoreService()
