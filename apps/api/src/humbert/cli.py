"""The Humbert CLI: ``init`` / ``connect`` / ``status`` / ``start``.

The commands are thin — they read and write ``config.json`` and delegate any
dbt/MetricFlow work to the engine adapter (the one seam that knows dbt).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import NoReturn

import typer

from humbert import __version__, engine, semantic
from humbert.config import (
    Config,
    Connection,
    config_path,
    humbert_home,
    load_config,
    project_dir,
    save_config,
)

app = typer.Typer(
    add_completion=False,
    help="Humbert — a light, local-first analytics notebook.",
)


@app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", help="Show the version and exit."),
) -> None:
    if version:
        typer.echo(f"humbert {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


@app.command()
def init(name: str = typer.Argument("default", help="Project name.")) -> None:
    """Scaffold ``~/.humbert/`` and register a project. Idempotent."""
    config: Config = load_config()
    cache = project_dir(name)
    cache.mkdir(parents=True, exist_ok=True)
    save_config(config)  # ensures config.json exists
    typer.echo(f"Initialised Humbert project '{name}'.")
    typer.echo(f"  config: {config_path()}")
    typer.echo(f"  cache:  {cache}")


@app.command()
def connect(
    project: Path = typer.Argument(..., help="Path to a dbt project."),
    name: str | None = typer.Option(None, "--name", "-n", help="Connection name."),
    schema: str = typer.Option(
        "marts", "--schema", help="Comma-separated dbt layer(s) to expose to Tier 2."
    ),
    build: bool = typer.Option(
        False, "--build", help="Force a rebuild even if the warehouse already exists."
    ),
) -> None:
    """Attach a dbt + MetricFlow source: validate, (auto-)build, record it."""
    project = project.expanduser().resolve()
    if not engine.is_dbt_project(project):
        _fail(f"{project} is not a dbt project (no dbt_project.yml).")

    name = name or project.name
    exposed = [s.strip() for s in schema.split(",") if s.strip()]
    warehouse = engine.warehouse_path(project)

    try:
        if build or not warehouse.exists():
            typer.echo(f"Building {project.name} …")
            engine.build(project)
        health = engine.introspect(project, exposed)
        _exposed_metrics, withheld = semantic.classify_metrics(project)
    except engine.EngineError as err:
        _fail(str(err))

    config = load_config()
    config.connections[name] = Connection(
        project_dir=str(project),
        exposed_schemas=exposed,
        warehouse_path=str(warehouse) if warehouse.exists() else None,
        built_at=datetime.now().strftime("%Y-%m-%d %H:%M") if warehouse.exists() else None,
        model_count=health.model_count,
        metric_count=health.metric_count,
        unavailable_count=health.unavailable_count,
        withheld_count=len(withheld),
    )
    config.active_connection = name
    project_dir(name).mkdir(parents=True, exist_ok=True)
    save_config(config)

    typer.echo(f"Connected '{name}' → {project}")
    typer.echo(
        f"  {health.model_count} models · {health.metric_count} metrics "
        f"· {health.unavailable_count} unavailable · {len(withheld)} withheld "
        f"  (exposed: {', '.join(exposed)})"
    )
    for issue in health.issues:
        marker = "!" if issue.severity == "fatal" else "·"
        typer.echo(f"  {marker} {issue.severity}: {issue.message.splitlines()[0]}")
    for item in withheld:
        typer.echo(f"  · withheld {item.metric}: {item.reason}")
    if withheld and not _exposed_metrics:
        typer.echo(
            "  All metrics withheld — classify the governed layer with "
            "`meta: {classification: open}` in dbt and reconnect."
        )


@app.command()
def status() -> None:
    """Show the active connection and current settings."""
    config = load_config()
    settings = config.settings
    connection = config.active

    if connection is None:
        typer.echo("No active connection.")
        typer.echo("Run `humbert connect <dbt-project>` to attach one.")
        typer.echo("")
        typer.echo(f"Skin:        {settings.theme}")
        typer.echo(f"Locale:      {settings.locale}")
        typer.echo(f"Config dir:  {humbert_home()}")
        return

    name = config.active_connection
    exposed = ", ".join(connection.exposed_schemas)
    health = _health_summary(connection)

    typer.echo(f"Connection:  {name}")
    typer.echo(f"Project:     {connection.project_dir}   (dbt + DuckDB)")
    typer.echo(f"Exposed:     {exposed}{health}")
    if connection.warehouse_path:
        built = f"   (built {connection.built_at})" if connection.built_at else ""
        typer.echo(f"Warehouse:   {connection.warehouse_path}{built}")
    typer.echo(f"Skin:        {settings.theme}")
    typer.echo(f"Locale:      {settings.locale}")
    typer.echo(f"Config dir:  {project_dir(name) if name else humbert_home()}")


def _health_summary(connection: Connection) -> str:
    """Render the ``(N models · M metrics · K unavailable)`` suffix, if known."""
    if connection.metric_count is None:
        return ""
    parts = []
    if connection.model_count is not None:
        parts.append(f"{connection.model_count} models")
    parts.append(f"{connection.metric_count} metrics")
    if connection.unavailable_count is not None:
        parts.append(f"{connection.unavailable_count} unavailable")
    if connection.withheld_count is not None:
        parts.append(f"{connection.withheld_count} withheld")
    return f"   ({' · '.join(parts)})"


@app.command()
def vocab() -> None:
    """List the metrics and dimensions the active source exposes."""
    project = _active_project()
    try:
        pack = semantic.load_pack(project)
    except engine.EngineError as err:
        _fail(str(err))

    if not pack.vocabulary.metrics:
        typer.echo("No metrics exposed by the active source.")
    for metric in pack.vocabulary.metrics:
        typer.echo(metric.name)
        for dim in metric.dimensions:
            grain = f"   grains: {dim.grain}" if dim.kind == "time" and dim.grain else ""
            typer.echo(f"  {dim.name:<32} {dim.kind}{grain}")
    if pack.withheld:
        typer.echo("")
        typer.echo(f"Withheld by the public-only guard ({len(pack.withheld)}):")
        for item in pack.withheld:
            typer.echo(f"  · {item.metric}: {item.reason}")


@app.command()
def query(
    metric: list[str] = typer.Option(..., "--metric", "-m", help="Metric to query (repeatable)."),
    by: list[str] = typer.Option([], "--by", help="Dimension to group by (repeatable)."),
    where: list[str] = typer.Option(
        [], "--where", help="MetricFlow filter expression (repeatable, passed through)."
    ),
    order: list[str] = typer.Option(
        [], "--order", help="Order by a metric/dimension; prefix '-' for descending (repeatable)."
    ),
    limit: int | None = typer.Option(None, "--limit", help="Max rows to return."),
    grain: str | None = typer.Option(
        None, "--grain", help="Time grain for grouped time dimensions (e.g. year)."
    ),
    sql: bool = typer.Option(False, "--sql", help="Also print the compiled SQL."),
) -> None:
    """Resolve a selection against the vocabulary and run it. Unknown names are reported."""
    project = _active_project()
    selection = semantic.Selection(
        metrics=metric,
        group_by=by,
        where=where,
        order_by=order,
        limit=limit,
        time_grain=grain,
    )
    try:
        vocabulary = semantic.discover_vocabulary(project)
    except engine.EngineError as err:
        _fail(str(err))

    resolved = semantic.resolve(selection, vocabulary)
    if isinstance(resolved, semantic.Unresolved):
        typer.echo("Selection did not resolve:", err=True)
        for problem in resolved.problems:
            typer.echo(f"  · {problem}", err=True)
        raise typer.Exit(1)

    try:
        result = semantic.run(resolved, vocabulary, project)
    except engine.EngineError as err:
        _fail(str(err))

    _print_table(result.columns, result.rows)
    if sql:
        typer.echo("")
        typer.echo(result.compiled_sql)


def _active_project() -> Path:
    """The active connection's dbt project dir, or fail with direction."""
    connection = load_config().active
    if connection is None:
        _fail("No active connection. Run `humbert connect <dbt-project>` first.")
    return Path(connection.project_dir)


def _print_table(columns: list[str], rows: list[list[str]]) -> None:
    """Print rows as a simple fixed-width table."""
    if not columns:
        typer.echo("(no rows)")
        return
    widths = [len(c) for c in columns]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(widths):
                widths[i] = max(widths[i], len(cell))
    header = "  ".join(c.ljust(widths[i]) for i, c in enumerate(columns))
    typer.echo(header)
    typer.echo("  ".join("-" * w for w in widths))
    for row in rows:
        typer.echo("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))


@app.command()
def start(
    port: int = typer.Option(8000, "--port", "-p", help="Port to serve on."),
    no_browser: bool = typer.Option(False, "--no-browser", help="Don't open the browser."),
) -> None:
    """Boot the runtime and serve the UI against the active connection."""
    import webbrowser

    import uvicorn

    from humbert.server import create_app

    config = load_config()
    connection = config.active_connection or "none"
    typer.echo(f"Humbert on http://localhost:{port}  ·  connection: {connection}")

    server = create_app(config)
    if not no_browser:
        webbrowser.open(f"http://localhost:{port}")
    uvicorn.run(server, host="127.0.0.1", port=port, log_level="info")


def _fail(message: str) -> NoReturn:
    typer.echo(message, err=True)
    raise typer.Exit(1)


def main() -> None:
    app()
