import asyncio
import threading
from typing import Any
from langchain_qdrant import QdrantVectorStore
from app.graph.nodes.common import get_query
from app.graph.state import SelfRagState
COLLECTION_NAME = "self rag"
DEFAULT_TOP_K = 4
_vector_store: QdrantVectorStore | None = None
_vector_store_lock = threading.Lock()
def _get_vector_store() -> QdrantVectorStore:
    global _vector_store
    if _vector_store is None:
        with _vector_store_lock:
            if _vector_store is None:
                from app.core.config import get_settings
                from app.rag.embedding import embeddings_ai
                settings = get_settings()
                _vector_store = QdrantVectorStore.from_existing_collection(
                    embedding=embeddings_ai,
                    url=settings.QDRANT_URL.get_secret_value(),
                    api_key=settings.QDRANT_API_KEY.get_secret_value(),
                    collection_name=COLLECTION_NAME,
                )
    return _vector_store
async def retrieve_node(state: SelfRagState) -> dict[str, Any]:
    """Retrieve the most relevant indexed climate documents for the user query."""
    query = get_query(state)
    vector_store = await asyncio.to_thread(_get_vector_store)
    documents = await vector_store.asimilarity_search(query, k=DEFAULT_TOP_K)
    return {
        "query": query,
        "documents": documents,
        "retrieved_node": "documents_retrieved" if documents else "no_documents_found",
        "retrieval_attempts": state.get("retrieval_attempts", 0) + 1,
    }
