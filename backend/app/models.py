from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

FileKind = Literal["pdf", "audio", "video"]
FileStatus = Literal["pending", "processing", "ready", "failed"]


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: EmailStr
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class FileOut(BaseModel):
    id: str
    filename: str
    kind: FileKind
    status: FileStatus
    size_bytes: int
    duration_seconds: float | None = None
    summary: str | None = None
    created_at: datetime
    error: str | None = None


class ChunkOut(BaseModel):
    id: str
    file_id: str
    chunk_index: int
    text: str
    start_time: float | None = None
    end_time: float | None = None


class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str


class ChatRequest(BaseModel):
    file_id: str
    question: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=4, ge=1, le=20)


class ChatCitation(BaseModel):
    chunk_id: str
    chunk_index: int
    text: str
    start_time: float | None = None
    end_time: float | None = None
    score: float


class ChatResponse(BaseModel):
    answer: str
    citations: list[ChatCitation] = []


class TimestampRequest(BaseModel):
    file_id: str
    topic: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=5, ge=1, le=20)


class TimestampHit(BaseModel):
    chunk_id: str
    text: str
    start_time: float
    end_time: float
    score: float


class TimestampResponse(BaseModel):
    hits: list[TimestampHit]


class SummaryResponse(BaseModel):
    file_id: str
    summary: str
