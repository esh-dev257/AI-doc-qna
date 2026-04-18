from datetime import datetime, timezone
from pathlib import Path

import aiofiles
from bson import ObjectId
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse

from app.config import get_settings
from app.database import get_db
from app.deps import api_keys_from_headers, get_current_user, get_llm_for_request
from app.models import DiagramResponse, FileOut, SummaryResponse
from app.services.extraction import detect_kind
from app.services.ingestion import delete_file_blob, ingest_file
from app.services.llm import LLMClient


ALLOWED_EXTENSIONS = {
    "pdf": {"pdf"},
    "audio": {"mp3", "wav", "m4a"},
    "video": {"mp4", "mov", "webm"},
}
ALLOWED_ALL = {ext for exts in ALLOWED_EXTENSIONS.values() for ext in exts}

router = APIRouter(prefix="/files", tags=["files"])


def _serialize(doc: dict) -> FileOut:
    return FileOut(
        id=str(doc["_id"]),
        filename=doc["filename"],
        kind=doc["kind"],
        status=doc.get("status", "pending"),
        size_bytes=int(doc.get("size_bytes", 0)),
        duration_seconds=doc.get("duration_seconds"),
        summary=doc.get("summary"),
        created_at=doc.get("created_at", datetime.now(timezone.utc)),
        error=doc.get("error"),
    )


@router.post("", response_model=FileOut, status_code=status.HTTP_201_CREATED)
async def upload_file(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
    api_keys: dict = Depends(api_keys_from_headers),
) -> FileOut:
    settings = get_settings()
    name = (file.filename or "").lower()
    ext = Path(name).suffix.lstrip(".")
    if ext not in ALLOWED_ALL:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Unsupported file type '.{ext}'. Allowed: PDF, MP3, WAV, M4A, MP4, MOV, WebM.",
        )
    try:
        kind = detect_kind(file.filename or "", file.content_type)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    if ext not in ALLOWED_EXTENSIONS.get(kind, set()):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Extension .{ext} is not allowed for {kind} files.",
        )

    content = await file.read()
    size = len(content)
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if size == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty file")
    if size > max_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File too large")

    db = get_db()
    now = datetime.now(timezone.utc)
    doc = {
        "owner_id": user["id"],
        "filename": file.filename,
        "kind": kind,
        "status": "pending",
        "size_bytes": size,
        "content_type": file.content_type,
        "created_at": now,
    }
    result = await db.files.insert_one(doc)
    file_id = str(result.inserted_id)

    safe_name = f"{file_id}_{Path(file.filename or 'upload').name}"
    stored_path = settings.upload_path / safe_name
    async with aiofiles.open(stored_path, "wb") as fh:
        await fh.write(content)

    await db.files.update_one(
        {"_id": result.inserted_id},
        {"$set": {"storage_path": str(stored_path)}},
    )

    background.add_task(_run_ingest, file_id, str(stored_path), kind, api_keys)

    doc["_id"] = result.inserted_id
    doc["storage_path"] = str(stored_path)
    return _serialize(doc)


async def _run_ingest(file_id: str, path: str, kind: str, api_keys: dict | None = None) -> None:
    try:
        await ingest_file(file_id, path, kind, api_keys=api_keys)
    except Exception:
        pass


@router.get("", response_model=list[FileOut])
async def list_files(user: dict = Depends(get_current_user)) -> list[FileOut]:
    db = get_db()
    cursor = db.files.find({"owner_id": user["id"]}).sort("created_at", -1)
    return [_serialize(doc) async for doc in cursor]


@router.get("/{file_id}", response_model=FileOut)
async def get_file(file_id: str, user: dict = Depends(get_current_user)) -> FileOut:
    db = get_db()
    try:
        doc = await db.files.find_one({"_id": ObjectId(file_id), "owner_id": user["id"]})
    except Exception:
        doc = None
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    return _serialize(doc)


@router.get("/{file_id}/summary", response_model=SummaryResponse)
async def get_summary(file_id: str, user: dict = Depends(get_current_user)) -> SummaryResponse:
    db = get_db()
    try:
        doc = await db.files.find_one({"_id": ObjectId(file_id), "owner_id": user["id"]})
    except Exception:
        doc = None
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    return SummaryResponse(
        file_id=file_id,
        summary=doc.get("summary") or "",
        diagram=doc.get("summary_diagram") or "",
    )


@router.post("/{file_id}/summary/diagram", response_model=DiagramResponse)
async def generate_summary_diagram(
    file_id: str,
    user: dict = Depends(get_current_user),
    llm: LLMClient = Depends(get_llm_for_request),
) -> DiagramResponse:
    db = get_db()
    try:
        doc = await db.files.find_one({"_id": ObjectId(file_id), "owner_id": user["id"]})
    except Exception:
        doc = None
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    if doc.get("status") != "ready":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"File is not ready (status={doc.get('status')})",
        )
    cached = (doc.get("summary_diagram") or "").strip()
    if cached:
        return DiagramResponse(file_id=file_id, diagram=cached)

    # Build source text: prefer the stored summary (short + focused), fall
    # back to joined chunks if there isn't one.
    source = (doc.get("summary") or "").strip()
    if not source:
        chunks = db.chunks.find({"file_id": file_id}).sort("chunk_index", 1)
        source = "\n\n".join([c.get("text", "") async for c in chunks])[:8000]
    if not source:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No content available")

    diagram = await llm.generate_diagram(source)
    await db.files.update_one(
        {"_id": ObjectId(file_id)},
        {"$set": {"summary_diagram": diagram}},
    )
    return DiagramResponse(file_id=file_id, diagram=diagram)


@router.get("/{file_id}/media")
async def stream_media(file_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    try:
        doc = await db.files.find_one({"_id": ObjectId(file_id), "owner_id": user["id"]})
    except Exception:
        doc = None
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    path = doc.get("storage_path")
    if not path or not Path(path).exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Blob missing")
    return FileResponse(
        path,
        media_type=doc.get("content_type") or "application/octet-stream",
        filename=doc.get("filename"),
    )


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(file_id: str, user: dict = Depends(get_current_user)) -> None:
    db = get_db()
    try:
        doc = await db.files.find_one_and_delete({"_id": ObjectId(file_id), "owner_id": user["id"]})
    except Exception:
        doc = None
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    await db.chunks.delete_many({"file_id": file_id})
    if doc.get("storage_path"):
        delete_file_blob(doc["storage_path"])
