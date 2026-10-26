"""FastAPI router for authenticated web chat sessions."""
from __future__ import annotations

import jwt
from typing import Optional
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator

from ...auth.service import read_access_token
from ...core.config import get_settings
from ...retrieval_orchestration.chat_types import ChatError
from ...retrieval_orchestration.postgres_sessions import PostgresSessionStore

router = APIRouter(prefix="/api/research/chat", tags=["research-chat"])

_bearer_scheme = HTTPBearer(auto_error=False)
_market_services = (None, None)


def configure_market_services(live=None, news=None):
    """Bind existing app services; never create a second collector for chat."""
    global _market_services
    _market_services = (live, news)
    get_store.cache_clear()


@lru_cache(maxsize=1)
def get_store() -> PostgresSessionStore:
    """Web history always uses Postgres, including fixture-mode web sessions."""
    from ...core.db import get_pool
    settings = get_settings()
    engine = None
    if settings.research_chat_live:
        from ...documents.embeddings import get_embedding_service
        from ...retrieval_orchestration.live_research import DenseEvidenceRetriever, LiveResearchService
        from ...b1_answering.core.policy import Limits
        from ...b1_answering.providers.gemini import GeminiProvider
        from ...retrieval_orchestration.market_research import MarketResearch
        from ...market_data.repository import FileMarketDataRepository
        limits = Limits.load()
        provider = None
        if settings.gemini_api_key.get_secret_value() and settings.b1_gemini_free_tier_confirmed:
            provider = GeminiProvider(limits, api_key=settings.gemini_api_key.get_secret_value(),
                                      free_tier_confirmed=True)
        engine = LiveResearchService(
            DenseEvidenceRetriever(get_pool(), get_embedding_service(),
                                   corpus_version_id=settings.research_corpus_version_id,
                                   model_ref=settings.embedding_model_ref,
                                   backend=settings.research_retrieval_backend),
            provider=provider, limits=limits,
            retrieval_timeout=settings.research_retrieval_timeout_seconds,
            market=MarketResearch(FileMarketDataRepository(), services=lambda: _market_services),
        )
    return PostgresSessionStore(get_pool(), engine=engine)


def get_owner(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> str:
    """Extract and validate owner UUID from JWT token."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Thiếu thông tin xác thực.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    try:
        owner_id = read_access_token(token, get_settings())
        return str(owner_id)
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ hoặc đã hết hạn.",
            headers={"WWW-Authenticate": "Bearer"},
        )


class SendMessageRequest(BaseModel):
    model_config = {"extra": "forbid"}
    text: str = Field(..., min_length=1, max_length=4000)
    revision: int = Field(..., ge=0, strict=True)

    @field_validator("text")
    @classmethod
    def strip_text(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Nội dung tin nhắn không được trống.")
        return v.strip()


class SessionSnapshot(BaseModel):
    session_id: str
    revision: int
    messages: list
    context: str
    execution_mode: str = "FIXTURE"


class SessionDescriptor(BaseModel):
    session_id: str
    preview: str
    saved_at: str
    turns: int


class SessionListResponse(BaseModel):
    items: list[SessionDescriptor]


@router.post("/sessions", response_model=SessionSnapshot, status_code=status.HTTP_201_CREATED)
async def create_session(
    owner: str = Depends(get_owner),
    store: PostgresSessionStore = Depends(get_store),
) -> dict:
    """Create a new chat session."""
    try:
        return await store.create(owner)
    except ChatError as e:
        raise HTTPException(status_code=e.status, detail=e.message)
    except Exception:
        raise HTTPException(status_code=503, detail="Lỗi hệ thống. Vui lòng thử lại.")


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    owner: str = Depends(get_owner),
    store: PostgresSessionStore = Depends(get_store),
) -> dict:
    """List all chat sessions for the authenticated user."""
    try:
        items = await store.list(owner)
        return {"items": items}
    except ChatError as e:
        raise HTTPException(status_code=e.status, detail=e.message)
    except Exception:
        raise HTTPException(status_code=503, detail="Lỗi hệ thống. Vui lòng thử lại.")


@router.get("/sessions/{session_id}", response_model=SessionSnapshot)
async def get_session(
    session_id: str,
    owner: str = Depends(get_owner),
    store: PostgresSessionStore = Depends(get_store),
) -> dict:
    """Get a specific chat session."""
    try:
        return await store.get(owner, session_id)
    except ChatError as e:
        raise HTTPException(status_code=e.status, detail=e.message)
    except Exception:
        raise HTTPException(status_code=503, detail="Lỗi hệ thống. Vui lòng thử lại.")


@router.post("/sessions/{session_id}/messages", response_model=SessionSnapshot)
async def send_message(
    session_id: str,
    body: SendMessageRequest,
    owner: str = Depends(get_owner),
    store: PostgresSessionStore = Depends(get_store),
) -> dict:
    """Send a message to a chat session."""
    try:
        return await store.send(owner, session_id, body.text, body.revision)
    except ChatError as e:
        raise HTTPException(status_code=e.status, detail=e.message)
    except Exception:
        raise HTTPException(status_code=503, detail="Lỗi hệ thống. Vui lòng thử lại.")


@router.post("/sessions/{session_id}/resume", response_model=SessionSnapshot, status_code=status.HTTP_201_CREATED)
async def resume_session(
    session_id: str,
    owner: str = Depends(get_owner),
    store: PostgresSessionStore = Depends(get_store),
) -> dict:
    """Resume a chat session as a new child session."""
    try:
        return await store.resume(owner, session_id)
    except ChatError as e:
        raise HTTPException(status_code=e.status, detail=e.message)
    except Exception:
        raise HTTPException(status_code=503, detail="Lỗi hệ thống. Vui lòng thử lại.")


@router.delete('/sessions/{session_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: str, owner: str = Depends(get_owner),
                         store: PostgresSessionStore = Depends(get_store)):
    try:
        await store.delete(owner, session_id)
    except ChatError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message)
    except Exception:
        raise HTTPException(status_code=503, detail='Lỗi hệ thống. Vui lòng thử lại.')
