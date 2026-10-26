from typing import Annotated, NotRequired, TypedDict
from langgraph.graph import add_messages
from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
class SelfRagState(TypedDict):
    """Shared state passed between the Self-RAG workflow nodes."""

    messages: Annotated[list[BaseMessage], add_messages]
    query: NotRequired[str]
    documents: NotRequired[list[Document]]
    generation: NotRequired[str]
    retrieved_node: NotRequired[str]
    is_correct_retrieved: NotRequired[bool]
    response_node: NotRequired[str]
    is_correct_response: NotRequired[bool]
    is_grounded: NotRequired[bool]
    is_useful: NotRequired[bool]
    revision_feedback: NotRequired[str]
    generation_attempts: NotRequired[int]
    retrieval_attempts: NotRequired[int]
