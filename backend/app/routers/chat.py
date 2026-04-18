import json

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.database import get_db
from app.deps import get_current_user, get_llm_for_request, user_rate_limit
from app.models import ChatCitation, ChatRequest, ChatResponse, TimestampHit, TimestampRequest, TimestampResponse
from app.services import cache
from app.services.llm import LLMClient
from app.services.vector_store import search

router = APIRouter(prefix="/chat", tags=["chat"])


SYSTEM_PROMPT = (
    "You are a helpful assistant that answers questions strictly based on the "
    "provided context. If the answer is not in the context, say so. "
    "When referencing media, cite the relevant timestamps when available."
)


async def _get_file_for_user(file_id: str, user_id: str) -> dict:
    db = get_db()
    try:
        doc = await db.files.find_one({"_id": ObjectId(file_id), "owner_id": user_id})
    except Exception:
        doc = None
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    if doc.get("status") != "ready":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"File is not ready (status={doc.get('status')})",
        )
    return doc


def _build_context(hits: list) -> str:
    parts = []
    for h in hits:
        ts = ""
        if h.start_time is not None and h.end_time is not None:
            ts = f" [t={h.start_time:.2f}-{h.end_time:.2f}s]"
        parts.append(f"(chunk {h.chunk_index}{ts})\n{h.text}")
    return "\n\n---\n\n".join(parts)


@router.post("", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    user: dict = Depends(user_rate_limit),
    llm: LLMClient = Depends(get_llm_for_request),
) -> ChatResponse:
    await _get_file_for_user(req.file_id, user["id"])
    cache_key = f"chat:{user['id']}:{req.file_id}:{req.top_k}:{req.question.strip().lower()}"
    cached = cache.get(cache_key)
    if cached:
        return ChatResponse(**cached)

    q_emb = (await llm.embed([req.question]))[0]
    hits = await search(req.file_id, q_emb, top_k=req.top_k)
    context = _build_context(hits)
    answer = await llm.chat(SYSTEM_PROMPT, req.question, context=context)

    citations = [
        ChatCitation(
            chunk_id=h.chunk_id,
            chunk_index=h.chunk_index,
            text=h.text[:400],
            start_time=h.start_time,
            end_time=h.end_time,
            score=h.score,
        )
        for h in hits
    ]
    response = ChatResponse(answer=answer, citations=citations)
    cache.set(cache_key, response.model_dump(), ttl=300)
    return response


@router.post("/stream")
async def chat_stream(
    req: ChatRequest,
    user: dict = Depends(user_rate_limit),
    llm: LLMClient = Depends(get_llm_for_request),
):
    await _get_file_for_user(req.file_id, user["id"])
    q_emb = (await llm.embed([req.question]))[0]
    hits = await search(req.file_id, q_emb, top_k=req.top_k)
    context = _build_context(hits)

    async def gen():
        citations = [
            {
                "chunk_id": h.chunk_id,
                "chunk_index": h.chunk_index,
                "text": h.text[:400],
                "start_time": h.start_time,
                "end_time": h.end_time,
                "score": h.score,
            }
            for h in hits
        ]
        yield f"event: citations\ndata: {json.dumps(citations)}\n\n"
        async for token in llm.stream_chat(SYSTEM_PROMPT, req.question, context=context):
            yield f"event: token\ndata: {json.dumps(token)}\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/timestamps", response_model=TimestampResponse)
async def timestamps(
    req: TimestampRequest,
    user: dict = Depends(user_rate_limit),
    llm: LLMClient = Depends(get_llm_for_request),
) -> TimestampResponse:
    doc = await _get_file_for_user(req.file_id, user["id"])
    if doc.get("kind") not in ("audio", "video"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Timestamps only apply to audio/video")
    q_emb = (await llm.embed([req.topic]))[0]
    hits = await search(req.file_id, q_emb, top_k=req.top_k)
    out: list[TimestampHit] = []
    for h in hits:
        if h.start_time is None or h.end_time is None:
            continue
        out.append(
            TimestampHit(
                chunk_id=h.chunk_id,
                text=h.text[:400],
                start_time=h.start_time,
                end_time=h.end_time,
                score=h.score,
            )
        )
    return TimestampResponse(hits=out)
