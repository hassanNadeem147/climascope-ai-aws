from typing import Literal

from app.graph.state import SelfRagState

MAX_GENERATION_ATTEMPTS = 2
ResponseGradeRoute = Literal["accept", "revise", "fallback"]


def route_after_response_grading(state: SelfRagState) -> ResponseGradeRoute:
    """Accept good answers, retry once, then use a safe fallback."""
    if state.get("is_grounded", False) and state.get("is_useful", False):
        return "accept"
    if state.get("generation_attempts", 0) < MAX_GENERATION_ATTEMPTS:
        return "revise"
    return "fallback"
