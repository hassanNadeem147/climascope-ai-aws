import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage

from app.api.dependencies import get_current_user
from app.logging.logger import logger
from app.models.user import User
from app.schemas.chat import ChatRequest


router = APIRouter(prefix="/model", tags=["model"])


def _event(event_name: str, payload: dict[str, Any]) -> str:
    return f"event: {event_name}\ndata: {json.dumps(payload, ensure_ascii=True)}\n\n"


def _chunk_text(chunk: Any) -> str:
    content = getattr(chunk, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block["text"]
            for block in content
            if isinstance(block, dict) and isinstance(block.get("text"), str)
        )
    return ""


@router.post("/stream")
async def stream_model_response(
    payload: ChatRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Stream model tokens as SSE and checkpoint each user-scoped thread."""
    workflow = getattr(request.app.state, "workflow", None)
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The model workflow is not available.",
        )

    client_thread_id = payload.thread_id or str(uuid4())
    checkpoint_thread_id = f"{current_user.id}:{client_thread_id}"
    graph_config = {"configurable": {"thread_id": checkpoint_thread_id}}

    async def generate_events() -> AsyncIterator[str]:
        yield _event("thread", {"thread_id": client_thread_id})
        try:
            async for event in workflow.astream_events(
                {
                    "query": payload.query,
                    "messages": [HumanMessage(content=payload.query)],
                },
                config=graph_config,
                version="v2",
            ):
                metadata = event.get("metadata") or {}
                if (
                    event.get("event") == "on_chat_model_stream"
                    and metadata.get("langgraph_node") == "generate"
                ):
                    data = event.get("data") or {}
                    text = _chunk_text(data.get("chunk"))
                    if text:
                        yield _event("token", {"text": text})
            yield _event("done", {"thread_id": client_thread_id})
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "Model stream failed for user {} and thread {}.",
                current_user.id,
                client_thread_id,
            )
            yield _event(
                "error",
                {
                    "detail": "The model could not complete this request.",
                    "thread_id": client_thread_id,
                },
            )

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Thread-ID": client_thread_id,
        },
    )