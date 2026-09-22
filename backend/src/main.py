"""FinMind prototype API."""

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field, field_validator

from .graph.text2cypher_service import (
    ReadOnlyCypherError,
    Text2CypherService,
    Text2CypherServiceError,
)


app = FastAPI(title="FinMind API", version="0.1.0")


class GraphQueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)

    @field_validator("question", mode="before")
    @classmethod
    def normalize_question(cls, value):
        if isinstance(value, str):
            value = value.strip()
        if not value:
            raise ValueError("question must not be blank")
        return value


class GraphQueryResponse(BaseModel):
    question: str
    cypher: str | None
    records: list[dict[str, Any]]
    error: str | None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/graph/query", response_model=GraphQueryResponse)
def graph_query(request: GraphQueryRequest) -> GraphQueryResponse:
    service = None
    try:
        service = Text2CypherService.from_environment()
        result = service.query(request.question)
        return GraphQueryResponse(
            question=result.question,
            cypher=result.cypher,
            records=result.records,
            error=result.error,
        )
    except (ReadOnlyCypherError, Text2CypherServiceError) as exc:
        return GraphQueryResponse(
            question=request.question,
            cypher=None,
            records=[],
            error=str(exc),
        )
    except Exception:
        return GraphQueryResponse(
            question=request.question,
            cypher=None,
            records=[],
            error="Graph query failed; check Neo4j and Text2Cypher configuration",
        )
    finally:
        if service is not None:
            service.close()
