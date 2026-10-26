from langchain_groq import ChatGroq
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from app.core.config import get_settings
from app.graph.nodes import (
    create_generate_node,
    create_grade_documents_node,
    create_grade_response_node,
    fallback_node,
    retrieve_node,
)
from app.graph.routers import (
    route_after_document_grading,
    route_after_response_grading,
    route_after_retrieval,
)
from app.graph.state import SelfRagState
def build_workflow(
    chat_model: BaseChatModel,
    checkpointer: BaseCheckpointSaver | None = None,
):
    """Build and compile the async Self-RAG graph using the supplied chat model."""
    graph = StateGraph(SelfRagState)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("grade_documents", create_grade_documents_node(chat_model))
    graph.add_node("generate", create_generate_node(chat_model))
    graph.add_node("grade_response", create_grade_response_node(chat_model))
    graph.add_node("fallback", fallback_node)
    graph.add_edge(START, "retrieve")
    graph.add_conditional_edges(
        "retrieve",
        route_after_retrieval,
        {
            "grade_documents": "grade_documents",
            "no_relevant_documents": "fallback",
        },
    )
    graph.add_conditional_edges(
        "grade_documents",
        route_after_document_grading,
        {
            "generate": "generate",
            "no_relevant_documents": "fallback",
        },
    )
    graph.add_edge("generate", "grade_response")
    graph.add_conditional_edges(
        "grade_response",
        route_after_response_grading,
        {
            "accept": END,
            "revise": "generate",
            "fallback": "fallback",
        },
    )
    graph.add_edge("fallback", END)

    return graph.compile(checkpointer=checkpointer)


def create_workflow(checkpointer: BaseCheckpointSaver | None = None):
    """Create the production graph with Groq credentials and model from Settings.

    Invoke the returned graph asynchronously with ``await graph.ainvoke(state)``.
    """
    settings = get_settings()
    chat_model = ChatGroq(
        api_key=settings.GROQ_API_KEY.get_secret_value(),
        model=settings.GROQ_MODEL,
        temperature=0,
    )
    return build_workflow(chat_model, checkpointer=checkpointer)