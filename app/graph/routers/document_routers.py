from typing import Literal

from app.graph.state import SelfRagState

RetrievalRoute = Literal["grade_documents", "no_relevant_documents"]
DocumentGradeRoute = Literal["generate", "no_relevant_documents"]


def route_after_retrieval(state: SelfRagState) -> RetrievalRoute:
    """Skip relevance grading when retrieval returned no documents."""
    if state.get("documents"):
        return "grade_documents"
    return "no_relevant_documents"


def route_after_document_grading(state: SelfRagState) -> DocumentGradeRoute:
    """Choose the relevant-context or no-relevant-context graph branch."""
    if state.get("documents"):
        return "generate"
    return "no_relevant_documents"
