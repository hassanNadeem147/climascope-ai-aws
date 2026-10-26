import time
from langchain_qdrant import QdrantVectorStore
from app.core.config import get_settings
from app.rag.embedding import embeddings_ai
from app.rag.splitter import split_docs
settings = get_settings()
def store_docs():
    """Embed PDF chunks and save them in Qdrant Cloud."""
    # Load all text chunks
    chunks = split_docs()
    if not chunks:
        print("No chunks found.")
        return
    batch_size = 20
    vector_store = None
    total_chunks = len(chunks)
    # Process a small batch at a time
    for start in range(0, total_chunks, batch_size):
        batch = chunks[start:start + batch_size]
        # Create the collection with the first batch
        if vector_store is None:
            vector_store = QdrantVectorStore.from_documents(
                documents=batch,
                embedding=embeddings_ai,
                url=settings.QDRANT_URL.get_secret_value(),
                api_key=settings.QDRANT_API_KEY.get_secret_value(),
                collection_name="self rag",
            )
        # Add the remaining batches to the same collection
        else:
            vector_store.add_documents(batch)
        processed = min(start + len(batch), total_chunks)
        print(f"Uploaded {processed}/{total_chunks} chunks")
        # Pause briefly between batches
        if processed < total_chunks:
            time.sleep(1)
    print("All chunks uploaded successfully!")
    return vector_store
if __name__ == "__main__":
    store_docs()