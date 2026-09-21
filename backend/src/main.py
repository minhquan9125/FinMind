"""FastAPI entrypoint for the FinMind backend.

Currently wires up only the Vector RAG module (document ingestion + vector
search), which is the B1 baseline described in the project proposal
(Section 6.5, Table 13). Structured Retrieval, the Neo4j graph branch,
Evidence Gate, Answer Verification and Gemini synthesis are separate,
not-yet-implemented modules (see readmerepair.md for what is and is not
covered by this change) and are intentionally left out of this app so the
API surface matches only what has actually been built.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import connect, disconnect
from .routers import documents, search

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    await connect()
    yield
    await disconnect()


app = FastAPI(title="FinMind Vector RAG API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)
app.include_router(search.router)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)

