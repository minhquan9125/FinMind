"""Validated output contracts; these models do not execute retrieval."""

from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RouterScope(BaseModel):
    """Resolved scope. Missing values remain empty until clarification."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    companies: list[str] = Field(default_factory=list)
    periods: list[str] = Field(default_factory=list)
    metric_code: str | None = Field(default=None, min_length=1)
    topic: str | None = Field(default=None, min_length=1)
    detected_industry: str | None = Field(default=None, min_length=1)
    entity_mentions: list[str] = Field(default_factory=list)
    measure_basis: str | None = None
    reporting_entity: str | None = None


class RouterTask(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(min_length=1)
    adapter: Literal["GRAPH", "CONTENT", "VECTOR"]
    operation: str = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)
    depends_on: str | None = Field(default=None, min_length=1)


class RouterOutput(BaseModel):
    """MVP contract: SEARCH or ASK_CLARIFICATION, not all LIVE statuses."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    decision: Literal["SEARCH", "ASK_CLARIFICATION"]
    route: Literal["VECTOR", "GRAPH", "BOTH", "CLARIFY"]
    scope: RouterScope
    missing_fields: list[str] = Field(default_factory=list)
    tasks: list[RouterTask] = Field(default_factory=list)
    clarification_question: str | None = Field(default=None, min_length=1)
    request_id: str | None = None
    reason_code: str | None = None
    route_reason: str | None = None
    model_version: str | None = None
    execution_mode: Literal["MOCK", "SHADOW", "LIVE"] = "MOCK"

    @model_validator(mode="after")
    def validate_execution_plan(self) -> Self:
        if self.decision == "ASK_CLARIFICATION":
            if self.route != "CLARIFY" or self.tasks:
                raise ValueError("ASK_CLARIFICATION requires CLARIFY and no tasks")
            if not self.clarification_question:
                raise ValueError("Clarification requires a useful question")
            return self

        if self.route == "CLARIFY":
            raise ValueError("SEARCH cannot use CLARIFY")
        if self.missing_fields or self.clarification_question is not None:
            raise ValueError("SEARCH cannot contain unresolved clarification")
        company_optional = (
            self.scope.topic in {"EVENT_IMPACT", "MARKET_DAILY_DIGEST"}
            or self.scope.detected_industry is not None
            or bool(self.scope.entity_mentions)
        )
        if ((not self.scope.companies and not company_optional)
                or any(not c.strip() for c in self.scope.companies)):
            raise ValueError("SEARCH requires resolved companies")
        if not self.tasks:
            raise ValueError("SEARCH requires at least one task")

        seen: dict[str, RouterTask] = {}
        for task in self.tasks:
            if task.id in seen:
                raise ValueError("Task IDs must be unique")
            if task.depends_on is not None and task.depends_on not in seen:
                raise ValueError("Dependencies must refer to earlier tasks")
            seen[task.id] = task

        adapters = {task.adapter for task in self.tasks}
        if self.route == "VECTOR" and not adapters <= {"CONTENT", "VECTOR"}:
            raise ValueError("VECTOR only permits content tasks")
        if self.route == "GRAPH" and adapters != {"GRAPH"}:
            raise ValueError("GRAPH only permits graph tasks")
        if self.route == "BOTH":
            if "GRAPH" not in adapters or not adapters & {"CONTENT", "VECTOR"}:
                raise ValueError("BOTH requires graph and content tasks")
            if not any(
                task.adapter in {"CONTENT", "VECTOR"}
                and task.depends_on is not None
                and seen[task.depends_on].adapter == "GRAPH"
                for task in self.tasks
            ):
                raise ValueError("MVP BOTH requires content depending on graph")
        return self
