"""HTTP API for the configured flow.

Run with `aikit serve`, or `uvicorn aikit.serving.api:app` (config from AIKIT_CONFIG).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable, Mapping
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from aikit.core.context import RunContext
from aikit.core.registry import KINDS, registry
from aikit.core.types import IngestReport, RunEvent, RunResult
from aikit.flows.base import collect_result
from aikit.runtime import Runtime, load_runtime


class Principal(BaseModel):
    user_id: str | None = None
    groups: list[str] = Field(default_factory=list)


def get_principal(
    x_user_id: Annotated[str | None, Header()] = None,
    x_user_groups: Annotated[str | None, Header()] = None,
) -> Principal:
    """Caller identity used for ACL filtering and audit logs.

    PLACEHOLDER: trusts headers set by a gateway. Replace this dependency with
    validation of your SSO/OIDC token before exposing the API.
    """
    groups = [g.strip() for g in (x_user_groups or "").split(",") if g.strip()]
    return Principal(user_id=x_user_id, groups=groups)


class RunRequest(BaseModel):
    input: str = Field(min_length=1)
    session_id: str | None = None
    stream: bool = True


class QueryRequest(BaseModel):
    input: str = Field(min_length=1)
    session_id: str | None = None


class ApproveRequest(BaseModel):
    approved: bool | dict[str, bool] = Field(
        default=False,
        description="true/false for all pending calls, or a map of call id to decision",
    )
    stream: bool = False


def runtime_dep(request: Request) -> Runtime:
    return request.app.state.runtime


RuntimeDep = Annotated[Runtime, Depends(runtime_dep)]
PrincipalDep = Annotated[Principal, Depends(get_principal)]


def run_context(principal: Principal, session_id: str | None = None) -> RunContext:
    return RunContext(
        session_id=session_id, user_id=principal.user_id, groups=list(principal.groups)
    )


def _sse(events: AsyncIterator[RunEvent]) -> StreamingResponse:
    async def body() -> AsyncIterator[str]:
        async for item in events:
            yield f"event: {item.type}\ndata: {item.model_dump_json()}\n\n"

    return StreamingResponse(
        body(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def create_app(
    config_path: str | Path | None = None,
    *,
    overrides: Mapping[str, Any] | Iterable[str] | None = None,
    offline: bool | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        runtime = load_runtime(config_path, overrides=overrides, offline=offline)
        app.state.runtime = runtime
        try:
            yield
        finally:
            await runtime.aclose()

    app = FastAPI(title="aikit", version="0.1.0", lifespan=lifespan)

    @app.get("/health")
    async def health(runtime: RuntimeDep) -> dict[str, Any]:
        return {
            "status": "ok",
            "app": runtime.config.app.name,
            "flow": type(runtime.flow).__name__,
            "ingest": runtime.ingest is not None,
        }

    @app.get("/components")
    async def list_components() -> dict[str, list[str]]:
        return {kind: registry.names(kind) for kind in KINDS}

    @app.post("/ingest")
    async def ingest(runtime: RuntimeDep, principal: PrincipalDep) -> IngestReport:
        if runtime.ingest is None:
            raise HTTPException(400, "No ingest section in the config")
        return await runtime.ingest.run()

    @app.post("/query")
    async def query(body: QueryRequest, runtime: RuntimeDep, principal: PrincipalDep) -> RunResult:
        return await runtime.flow.run(body.input, run_context(principal, body.session_id))

    @app.post("/runs", response_model=None)
    async def start_run(
        body: RunRequest, runtime: RuntimeDep, principal: PrincipalDep
    ) -> StreamingResponse | RunResult:
        events = runtime.flow.stream(body.input, run_context(principal, body.session_id))
        return _sse(events) if body.stream else await collect_result(events)

    @app.post("/runs/{run_id}/approve", response_model=None)
    async def approve_run(
        run_id: str, body: ApproveRequest, runtime: RuntimeDep, principal: PrincipalDep
    ) -> StreamingResponse | RunResult:
        flow: Any = runtime.flow
        if not hasattr(flow, "resume_stream"):
            raise HTTPException(400, "The configured flow does not support approvals")
        if await flow.pending(run_id) is None:
            raise HTTPException(404, f"No paused run with id '{run_id}'")
        events = flow.resume_stream(
            run_id, body.approved, RunContext(metadata={"approver": principal.user_id})
        )
        return _sse(events) if body.stream else await collect_result(events)

    return app


app = create_app()
