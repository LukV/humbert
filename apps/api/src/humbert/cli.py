"""The Humbert CLI: ``init`` / ``connect`` / ``status`` / ``start``.

The commands are thin — they read and write ``config.json`` and delegate any
dbt/MetricFlow work to the engine adapter (the one seam that knows dbt).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import NoReturn

import typer

from humbert import __version__, engine
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
    )
    config.active_connection = name
    project_dir(name).mkdir(parents=True, exist_ok=True)
    save_config(config)

    typer.echo(f"Connected '{name}' → {project}")
    typer.echo(
        f"  {health.model_count} models · {health.metric_count} metrics "
        f"· {health.unavailable_count} unavailable  (exposed: {', '.join(exposed)})"
    )
    for issue in health.issues:
        marker = "!" if issue.severity == "fatal" else "·"
        typer.echo(f"  {marker} {issue.severity}: {issue.message.splitlines()[0]}")


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
    return f"   ({' · '.join(parts)})"


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
