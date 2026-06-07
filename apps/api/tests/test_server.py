"""The runtime: bootstrap endpoint + skin/lang injection into the shell."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from humbert.config import Config
from humbert.server import create_app, inject_shell


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


def test_spa_without_build_is_graceful(tmp_path: Path) -> None:
    client = TestClient(create_app(Config(), dist=tmp_path))
    response = client.get("/anything")
    assert response.status_code == 200
    assert "not built" in response.text.lower()
