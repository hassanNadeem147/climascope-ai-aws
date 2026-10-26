from langchain_core.documents import Document
from langchain_core.messages import BaseMessage, HumanMessage
from app.graph.state import SelfRagState
def get_query(state: SelfRagState) -> str:
    query = state.get("query", "").strip()
    if query:
        return query
    for message in reversed(state.get("messages", [])):
        if isinstance(message, HumanMessage):
            content = message.content
            if isinstance(content, str) and content.strip():
                return content.strip()
    raise ValueError("Self-RAG state must contain a query or a user message.")
def format_document(document: Document) -> str:
    source = document.metadata.get("source", "unknown source")
    page = document.metadata.get("page")
    location = f"{source}, page {page}" if page is not None else str(source)
    return f"Source: {location}\nContent:\n{document.page_content}"
def message_text(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            block["text"]
            for block in content
            if isinstance(block, dict) and isinstance(block.get("text"), str)
        )
    return str(content)
