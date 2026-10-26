from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from app.rag.loader import load_docs
def split_docs() -> list[Document]:
    """Split PDF documents into smaller text chunks."""
    # Load text from the PDF files
    docs = load_docs()
    # Create a text splitter
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100,
    )
    # Split documents into smaller chunks
    chunks = text_splitter.split_documents(docs)
    # Return all the chunks
    return chunks
chunks = split_docs()