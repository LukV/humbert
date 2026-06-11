"""The runtime: bootstrap endpoint + skin/lang injection into the shell."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from humbert import orchestrator, semantic
from humbert.config import Config, Connection
from humbert.server import create_app, inject_shell


def _sse_events(text: str) -> list[tuple[str, Any]]:
    """Parse a Server-Sent Events body into (event, data) pairs."""
    events: list[tuple[str, Any]] = []
    event = ""
    for block in text.split("\n\n"):
        for line in block.splitlines():
            if line.startswith("event:"):
                event = line[len("event:") :].strip()
            elif line.startswith("data:"):
                events.append((event, json.loads(line[len("data:") :].strip())))
    return events


def _first_cell(text: str) -> Any:
    return next(data for event, data in _sse_events(text) if event == "cell")


def test_inject_shell_sets_skin_and_lang() -> None:
    html = '<!doctype html><html lang="nl" data-skin="humbert"><body>x</body></html>'
    out = inject_shell(html, skin="proef", locale="en")
    assert 'data-skin="proef"' in out
    assert 'lang="en"' in out
    assert "humbert" not in out


def test_bootstrap_endpoint_reflects_config(tmp_path: Path) -> None:
    cfg = Config()
    cfg.settings.theme = "proef"
    cfg.settings.locale = "nl"
    cfg.settings.app_name = "Proef"
    client = TestClient(create_app(cfg, dist=tmp_path))
    response = client.get("/api/bootstrap")
    assert response.status_code == 200
    assert response.json() == {"skin": "proef", "locale": "nl", "app_name": "Proef"}


def test_spa_injects_shell_from_config(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text(
        '<html lang="nl" data-skin="humbert"><body>hi</body></html>'
    )
    cfg = Config()
    cfg.settings.theme = "proef"
    cfg.settings.locale = "en"
    client = TestClient(create_app(cfg, dist=tmp_path))
    response = client.get("/")
    assert response.status_code == 200
    assert 'data-skin="proef"' in response.text
    assert 'lang="en"' in response.text


def test_theme_endpoint_falls_back_to_settings(tmp_path: Path) -> None:
    cfg = Config()
    cfg.settings.app_name = "Humbert"
    body = TestClient(create_app(cfg, dist=tmp_path)).get("/api/theme").json()
    assert body["app_name"] == "Humbert"
    assert body["custom_css"] is None
    assert body["css_vars"]["--accent"] == "#4A2D4F"  # the default skin


def test_theme_endpoint_reads_a_project_theme_json(home: Path) -> None:
    proj = home / "projects" / "cheese"
    proj.mkdir(parents=True)
    (proj / "theme.json").write_text(
        json.dumps(
            {
                "app_name": "proef",
                "locale": "nl",
                "colors": {"primary": "#2B979D", "palette": ["#2B979D", "#CC5621", "#5D6009"]},
                "fonts": {"body": "Flanders Art Sans", "custom_css": "/fonts/flanders-fonts.css"},
            }
        )
    )
    body = TestClient(create_app(_connected_config(), dist=home)).get("/api/theme").json()
    assert body["app_name"] == "proef"
    assert body["locale"] == "nl"
    assert body["custom_css"] == "/fonts/flanders-fonts.css"
    assert body["css_vars"]["--accent"] == "#2B979D"
    assert body["css_vars"]["--font-body"].startswith('"Flanders Art Sans"')
    assert "#2B979D" in body["css_vars"]["--chart-palette"]


def test_fonts_are_served_when_the_skin_ships_them(home: Path) -> None:
    (home / "fonts").mkdir()
    (home / "fonts" / "flanders-fonts.css").write_text("/* faces */")
    client = TestClient(create_app(_connected_config(), dist=home))
    response = client.get("/fonts/flanders-fonts.css")
    assert response.status_code == 200
    assert "/* faces */" in response.text


def test_spa_without_build_is_graceful(tmp_path: Path) -> None:
    client = TestClient(create_app(Config(), dist=tmp_path))
    response = client.get("/anything")
    assert response.status_code == 200
    assert "not built" in response.text.lower()


def test_unknown_api_path_is_404_not_the_spa(tmp_path: Path) -> None:
    """An unknown /api/* path must 404, not masquerade as the app shell (200)."""
    client = TestClient(create_app(Config(), dist=tmp_path))
    assert client.get("/api/does-not-exist").status_code == 404
    assert client.get("/api/pack").status_code == 404
    # A normal SPA route still serves the shell.
    assert client.get("/notebook").status_code == 200


# --- the notebook API -----------------------------------------------------


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HUMBERT_HOME", str(tmp_path))
    return tmp_path


def _connected_config() -> Config:
    cfg = Config()
    cfg.connections["cheese"] = Connection(project_dir="/x/cheese")
    cfg.active_connection = "cheese"
    return cfg


def _vocab() -> semantic.Vocabulary:
    return semantic.Vocabulary(
        metrics=[
            semantic.MetricInfo(
                name="total_production",
                dimensions=[semantic.DimensionInfo("cheese_record__country", "categorical")],
            )
        ]
    )


def _answer() -> orchestrator.Answer:
    return orchestrator.Answer(
        question="which countries produce the most cheese?",
        reading="read cheese as total_production, by country",
        selection=semantic.Selection(
            metrics=["total_production"], group_by=["cheese_record__country"]
        ),
        columns=["cheese_record__country", "total_production"],
        rows=[["Germany", "100"], ["France", "80"]],
        compiled_sql="SELECT ...",
        narrative="Germany leads.",
        certainty="high",
    )


def _stub_ask(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(semantic, "discover_vocabulary", lambda p: _vocab())
    monkeypatch.setattr(orchestrator, "build_model", lambda llm: object())
    monkeypatch.setattr(orchestrator, "ask", lambda *a, **k: _answer())


def test_notebook_requires_a_connection(tmp_path: Path) -> None:
    client = TestClient(create_app(Config(), dist=tmp_path))
    response = client.get("/api/notebook")
    assert response.status_code == 400
    assert "No active connection" in response.json()["error"]


def test_notebook_returns_a_cell_array(home: Path) -> None:
    client = TestClient(create_app(_connected_config(), dist=home))
    response = client.get("/api/notebook")
    assert response.status_code == 200
    assert response.json() == []


def test_ask_streams_a_cell_event(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_ask(monkeypatch)
    client = TestClient(create_app(_connected_config(), dist=home))
    response = client.post("/api/ask", json={"question": "which countries make the most?"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    cell = _first_cell(response.text)
    assert cell["id"] == "1"
    assert cell["refusal"] is None
    assert cell["chart"]["spec"]["layer"][0]["mark"]["type"] == "bar"
    assert cell["result"]["data"][0]["total_production"] == 100  # coerced to a number
    # And it persisted — a second read sees it.
    assert len(client.get("/api/notebook").json()) == 1


def test_followup_passes_prior_context_and_links_the_cell(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(semantic, "discover_vocabulary", lambda p: _vocab())
    monkeypatch.setattr(orchestrator, "build_model", lambda llm: object())
    captured: dict[str, object] = {}

    def fake_ask(question: str, **kwargs: object) -> orchestrator.Answer:
        captured.update(kwargs)
        return _answer()

    monkeypatch.setattr(orchestrator, "ask", fake_ask)
    client = TestClient(create_app(_connected_config(), dist=home))

    first = _first_cell(client.post("/api/ask", json={"question": "compare them"}).text)
    # The first ask has no parent.
    assert captured["prior_selection"] is None

    second = _first_cell(
        client.post("/api/ask", json={"question": "add Italy", "parent_cell_id": first["id"]}).text
    )
    # The follow-up carries the parent's selection + question, and links back.
    assert captured["prior_question"] == _answer().question
    assert captured["prior_selection"] is not None
    assert second["context"]["parent_cell_id"] == first["id"]


def test_patch_renames_a_cell(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_ask(monkeypatch)
    client = TestClient(create_app(_connected_config(), dist=home))
    cell = _first_cell(client.post("/api/ask", json={"question": "q"}).text)
    patched = client.patch(f"/api/cells/{cell['id']}", json={"title": "Cheese leaders"})
    assert patched.status_code == 200
    assert patched.json()["title"] == "Cheese leaders"


def test_ask_without_a_key_is_a_quiet_error(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(semantic, "discover_vocabulary", lambda p: _vocab())

    def _no_key(llm: object) -> object:
        raise orchestrator.OrchestratorError("No API key found in $ANTHROPIC_API_KEY.")

    monkeypatch.setattr(orchestrator, "build_model", _no_key)
    client = TestClient(create_app(_connected_config(), dist=home))
    response = client.post("/api/ask", json={"question": "anything"})
    assert response.status_code == 400
    assert "API key" in response.json()["error"]


def test_healthz_down_without_a_connection(tmp_path: Path) -> None:
    client = TestClient(create_app(Config(), dist=tmp_path))
    body = client.get("/api/healthz").json()
    assert body["status"] == "down"
    assert body["project"] is None


def test_healthz_ok_when_warehouse_and_metrics_present(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from humbert import engine

    warehouse = home / "warehouse.duckdb"
    warehouse.write_text("")
    monkeypatch.setattr(engine, "warehouse_path", lambda p: warehouse)
    monkeypatch.setattr(engine, "metric_names", lambda p: ["total_production", "product_variety"])

    client = TestClient(create_app(_connected_config(), dist=home))
    body = client.get("/api/healthz").json()
    assert body["status"] == "ok"
    assert body["project"] == "cheese"
    assert {"name": "metrics", "ok": True, "detail": "2 metrics"} in body["checks"]


def test_healthz_degraded_when_metrics_unreadable(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from humbert import engine

    warehouse = home / "warehouse.duckdb"
    warehouse.write_text("")
    monkeypatch.setattr(engine, "warehouse_path", lambda p: warehouse)

    def _broken(p: object) -> list[str]:
        raise engine.EngineError("no manifest")

    monkeypatch.setattr(engine, "metric_names", _broken)
    client = TestClient(create_app(_connected_config(), dist=home))
    assert client.get("/api/healthz").json()["status"] == "degraded"


def test_delete_removes_a_cell(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_ask(monkeypatch)
    client = TestClient(create_app(_connected_config(), dist=home))
    cell = _first_cell(client.post("/api/ask", json={"question": "q"}).text)

    deleted = client.delete(f"/api/cells/{cell['id']}")
    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": True}
    assert client.get("/api/notebook").json() == []
    # Idempotent — deleting again is a quiet no-op.
    assert client.delete(f"/api/cells/{cell['id']}").json() == {"deleted": False}
