from langchain_huggingface import HuggingFaceEmbeddings
embeddings_ai = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-mpnet-base-v2",
    model_kwargs={"device": "cpu"},  # e.g., "cuda" for GPU or "cpu"
    encode_kwargs={"normalize_embeddings": True}  # normalizes output vectors for cosine similarity
)


