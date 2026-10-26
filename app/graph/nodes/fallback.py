from typing import Any
from langchain_core.messages import AIMessage
from app.graph.state import SelfRagState
async def fallback_node(state: SelfRagState) -> dict[str, Any]:
    """Return a safe response when an answer fails quality checks after retry."""
    if not state.get("is_grounded", False):
        answer = (
            "I couldn't verify a reliable answer against the indexed climate "
            "documents. Please try rephrasing your question or ask about a "
            "specific topic covered by the sources."
        )
    else:
        answer = (
            "I couldn't produce a clear answer to that question from the indexed "
            "climate documents. Please try rephrasing it or narrowing its scope."
        )
    return {
        "generation": answer,
        "response_node": "answer_not_verified",
        "messages": [AIMessage(content=answer)],
    }
