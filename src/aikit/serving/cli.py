from __future__ import annotations

import asyncio
import inspect
import json
import sys
from collections.abc import AsyncIterator, Coroutine
from dataclasses import dataclass, field
from typing import Annotated, Any, TypeVar

import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from aikit.core.builder import param_hints, signature_model
from aikit.core.config import EvalDataset
from aikit.core.context import RunContext
from aikit.core.errors import AikitError, ConfigError
from aikit.core.registry import KINDS, registry
from aikit.core.types import Message, RunEvent, RunResult
from aikit.runtime import Runtime, load_runtime

app = typer.Typer(
    help="Build, run, and evaluate RAG and agent apps from a config file.",
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_show_locals=False,
)
console = Console()
err = Console(stderr=True)
T = TypeVar("T")


@dataclass
class Options:
    config: str | None = None
    offline: bool = False
    overrides: list[str] = field(default_factory=list)
    verbose: bool = False


@app.callback()
def main(
    ctx: typer.Context,
    config: Annotated[
        str | None,
        typer.Option(
            "--config", "-c", envvar="AIKIT_CONFIG", help="Config file (default project/app.yaml)."
        ),
    ] = None,
    offline: Annotated[
        bool, typer.Option("--offline", help="Replace every LLM and embedder with offline fakes.")
    ] = False,
    overrides: Annotated[
        list[str] | None,
        typer.Option("--set", "-s", help="Override a config value, e.g. -s flow.top_k=3"),
    ] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Show structured logs.")] = False,
) -> None:
    ctx.obj = Options(config=config, offline=offline, overrides=overrides or [], verbose=verbose)


def _options(ctx: typer.Context) -> Options:
    return ctx.obj if isinstance(ctx.obj, Options) else Options()


def _runtime(ctx: typer.Context) -> Runtime:
    opts = _options(ctx)
    try:
        return load_runtime(
            opts.config,
            overrides=opts.overrides,
            offline=opts.offline or None,
            log_level=None if opts.verbose else "WARNING",
        )
    except ConfigError as exc:
        err.print(f"[red]Config error:[/red] {escape(str(exc))}")
        raise typer.Exit(2) from exc


def _run(runtime: Runtime, coro: Coroutine[Any, Any, T]) -> T:
    async def wrapper() -> T:
        try:
            return await coro
        finally:
            await runtime.aclose()

    try:
        return asyncio.run(wrapper())
    except AikitError as exc:
        err.print(f"[red]{type(exc).__name__}:[/red] {escape(str(exc))}")
        raise typer.Exit(1) from exc


async def _render(events: AsyncIterator[RunEvent], *, verbose: bool, as_json: bool) -> RunResult:
    result: RunResult | None = None
    streamed = False
    for_humans = not as_json
    async for item in events:
        data = item.data
        if item.type == "token" and for_humans:
            sys.stdout.write(data["text"])
            sys.stdout.flush()
            streamed = True
        elif item.type == "answer" and for_humans and not streamed:
            console.print(escape(data["text"]))
        elif item.type == "retrieval" and verbose and for_humans:
            sources = ", ".join(str(c.get("source")) for c in data.get("chunks", []))
            console.print(f"[dim]retrieved {len(data.get('chunks', []))}: {escape(sources)}[/dim]")
        elif item.type == "tool_call" and verbose and for_humans:
            args = json.dumps(data.get("arguments", {}), ensure_ascii=False)
            console.print(f"[cyan]-> {data['name']}[/cyan]({escape(args)})")
        elif item.type == "tool_result" and verbose and for_humans:
            colour = "red" if data.get("is_error") else "green"
            console.print(f"[{colour}]<- {data['name']}[/{colour}] {escape(data['content'][:200])}")
        elif item.type == "error" and for_humans:
            err.print(f"[red]{escape(json.dumps(data))}[/red]")
        elif item.type == "done":
            result = RunResult.model_validate(data["result"])
    if streamed:
        sys.stdout.write("\n")
    if result is None:
        raise AikitError("Flow finished without a result")
    return result


def _print_footer(result: RunResult) -> None:
    for citation in result.citations:
        page = f", page {citation.page}" if citation.page else ""
        console.print(f"[dim][{citation.index}] {escape(str(citation.source))}{page}[/dim]")
    if result.status != "completed":
        console.print(f"[yellow]status: {result.status}[/yellow]")


@app.command()
def ingest(ctx: typer.Context) -> None:
    """Load, chunk, embed, and index the documents configured under `ingest`."""
    runtime = _runtime(ctx)
    if runtime.ingest is None:
        err.print("[red]No `ingest` section in the config.[/red]")
        raise typer.Exit(1)
    report = _run(runtime, runtime.ingest.run())
    table = Table(title="Ingest report")
    table.add_column("field")
    table.add_column("value", justify="right")
    for key, value in report.model_dump().items():
        table.add_row(key, str(value))
    console.print(table)


@app.command()
def ask(
    ctx: typer.Context,
    question: Annotated[str, typer.Argument(help="Question to answer.")],
    session: Annotated[str | None, typer.Option(help="Session id for conversation memory.")] = None,
    group: Annotated[
        list[str] | None, typer.Option(help="ACL group of the caller (repeatable).")
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Print the full result as JSON.")] = False,
) -> None:
    """Ask the configured flow a question and stream the answer."""
    runtime = _runtime(ctx)
    run_ctx = RunContext(session_id=session, groups=group or [])
    result = _run(
        runtime,
        _render(
            runtime.flow.stream(question, run_ctx), verbose=_options(ctx).verbose, as_json=as_json
        ),
    )
    if as_json:
        console.print_json(result.model_dump_json())
    else:
        _print_footer(result)


@app.command()
def run(
    ctx: typer.Context,
    task: Annotated[str, typer.Argument(help="Task for the agent.")],
    session: Annotated[str | None, typer.Option(help="Session id for conversation memory.")] = None,
    group: Annotated[
        list[str] | None, typer.Option(help="ACL group of the caller (repeatable).")
    ] = None,
    auto_approve: Annotated[
        bool, typer.Option(help="Approve every tool call without asking.")
    ] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Print the full result as JSON.")] = False,
) -> None:
    """Run a task, showing each step and asking before tools that need approval."""
    runtime = _runtime(ctx)
    flow = runtime.flow

    async def go() -> RunResult:
        result = await _render(
            flow.stream(task, RunContext(session_id=session, groups=group or [])),
            verbose=True,
            as_json=as_json,
        )
        resume = getattr(flow, "resume_stream", None)
        while result.status == "awaiting_approval" and resume is not None:
            approvals: dict[str, bool] = {}
            for call in result.pending_approvals:
                prompt = f"Approve {call.name}({json.dumps(call.arguments, ensure_ascii=False)})?"
                approvals[call.id] = auto_approve or typer.confirm(prompt, default=False)
            result = await _render(resume(result.run_id, approvals), verbose=True, as_json=as_json)
        return result

    result = _run(runtime, go())
    if as_json:
        console.print_json(result.model_dump_json())
    else:
        _print_footer(result)
        console.print(f"[dim]steps: {result.steps}, tokens: {result.usage.total_tokens}[/dim]")


@app.command("eval")
def eval_command(
    ctx: typer.Context,
    dataset: Annotated[
        list[str] | None, typer.Option("--dataset", "-d", help="JSONL dataset (repeatable).")
    ] = None,
    auto_approve: Annotated[
        bool | None, typer.Option("--auto-approve/--no-auto-approve", help="Approve tool calls.")
    ] = None,
    output: Annotated[str | None, typer.Option(help="Directory for the JSON report.")] = None,
    min_pass_rate: Annotated[
        float | None, typer.Option(help="Exit with code 1 if any pass rate is below this (0-1).")
    ] = None,
) -> None:
    """Run eval datasets against the active config and write a JSON report."""
    from aikit.evals import run_evals

    runtime = _runtime(ctx)
    datasets = [EvalDataset(path=p) for p in dataset] if dataset else None
    report = _run(
        runtime, run_evals(runtime, datasets, auto_approve=auto_approve, output_dir=output)
    )

    cases = Table(title=f"Eval cases ({report.app})")
    for column in ("id", "kind", "status", "passed", "metrics"):
        cases.add_column(column)
    for case in report.cases:
        metrics = ", ".join(
            f"{k}={v:.2f}" for k, v in case.metrics.items() if isinstance(v, int | float)
        )
        mark = "[green]yes[/green]" if case.passed else "[red]no[/red]"
        cases.add_row(case.id, case.kind, case.status, mark, metrics)
    console.print(cases)

    summary = Table(title="Summary")
    for column in ("kind", "metric", "value"):
        summary.add_column(column)
    for kind, stats in report.summary.items():
        for name, value in stats.items():
            summary.add_row(kind, name, "-" if value is None else f"{value:.3f}")
    console.print(summary)
    if report.path:
        console.print(f"[dim]report: {report.path}[/dim]")

    if min_pass_rate is not None:
        rates = [s.get("pass_rate") or 0.0 for s in report.summary.values()]
        if any(rate < min_pass_rate for rate in rates):
            err.print(f"[red]Pass rate below {min_pass_rate}[/red]")
            raise typer.Exit(1)


@app.command()
def components(
    ctx: typer.Context,
    kind: Annotated[str | None, typer.Option(help="Only list this kind.")] = None,
    schema: Annotated[
        str | None, typer.Option(help="Show parameters for one component, e.g. retriever/hybrid.")
    ] = None,
) -> None:
    """List registered components, or show the parameters one accepts."""
    try:
        _runtime(ctx)
    except typer.Exit:
        err.print("[yellow]Config failed to load; showing built-in components only.[/yellow]")

    if schema:
        kind_name, _, name = schema.partition("/")
        try:
            factory = registry.get(kind_name, name)
        except ConfigError as exc:
            err.print(f"[red]{escape(str(exc))}[/red]")
            raise typer.Exit(1) from exc
        console.print(f"[bold]{kind_name}/{name}[/bold]  ({factory.__module__})")
        doc = inspect.getdoc(factory)
        if doc:
            console.print(escape(doc) + "\n")
        model = signature_model(factory)
        hints = param_hints(factory)
        table = Table()
        for column in ("parameter", "type", "default"):
            table.add_column(column)
        for param, info in model.model_fields.items():
            hint = hints.get(param, info.annotation)
            annotation = getattr(hint, "__name__", None) or str(hint)
            default = "required" if info.is_required() else repr(info.default)
            table.add_row(param, escape(annotation.replace("typing.", "")), escape(default))
        console.print(table)
        return

    table = Table(title="Registered components")
    table.add_column("kind")
    table.add_column("names")
    for kind_name in KINDS:
        if kind and kind != kind_name:
            continue
        table.add_row(kind_name, ", ".join(registry.names(kind_name)) or "-")
    console.print(table)


@app.command()
def validate(
    ctx: typer.Context,
    ping: Annotated[bool, typer.Option(help="Also send a tiny request to every LLM.")] = False,
) -> None:
    """Load the config and build every component without running anything."""
    runtime = _runtime(ctx)
    try:
        built = runtime.builder.build_all()
    except ConfigError as exc:
        err.print(f"[red]Config error:[/red] {escape(str(exc))}")
        raise typer.Exit(2) from exc

    table = Table(title=f"{runtime.config.app.name}: config OK")
    table.add_column("component")
    table.add_column("class")
    for name, obj in built.items():
        table.add_row(name, type(obj).__name__)
    table.add_row("flow", type(runtime.flow).__name__)
    table.add_row("ingest", type(runtime.ingest).__name__ if runtime.ingest else "-")
    console.print(table)

    if ping:

        async def ping_all() -> None:
            for name, obj in built.items():
                if runtime.builder.kind_of(name) == "llm":
                    response = await obj.chat([Message.user("Reply with the word pong.")])
                    console.print(f"{name}: {escape((response.content or '').strip()[:80])}")

        _run(runtime, ping_all())


@app.command()
def serve(
    ctx: typer.Context,
    host: Annotated[str, typer.Option(help="Bind address.")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Port.")] = 8000,
) -> None:
    """Serve the configured flow over HTTP (needs the `api` extra)."""
    try:
        import uvicorn

        from aikit.serving.api import create_app
    except ImportError as exc:
        err.print("[red]Install the api extra: pip install 'aikit[api]'[/red]")
        raise typer.Exit(1) from exc
    opts = _options(ctx)
    uvicorn.run(
        create_app(opts.config, overrides=opts.overrides, offline=opts.offline or None),
        host=host,
        port=port,
    )


if __name__ == "__main__":
    app()
