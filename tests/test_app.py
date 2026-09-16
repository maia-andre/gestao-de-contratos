import ast
import os
import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

APP_DIR = Path(__file__).resolve().parent.parent / "app"
TEMPLATES_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"
DISALLOWED_MODULES = {"requests", "httpx", "aiohttp", "socket", "http", "urllib"}


def _imported_top_level_modules(py_file: Path) -> set[str]:
    tree = ast.parse(py_file.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])
    return modules


def test_home_page_responds_with_success():
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "Fiscalização de Contratos" in response.text


def test_home_page_requires_no_authentication():
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code not in (401, 403)
    assert "www-authenticate" not in response.headers


def test_server_starts_without_any_request_headers_or_credentials():
    with TestClient(app) as client:
        response = client.get("/", headers={})
    assert response.status_code == 200


def test_app_package_makes_no_external_network_calls():
    offending = []
    for py_file in APP_DIR.rglob("*.py"):
        hits = _imported_top_level_modules(py_file) & DISALLOWED_MODULES
        if hits:
            offending.append((str(py_file), sorted(hits)))
    assert not offending, f"Módulos de rede externa encontrados: {offending}"


def test_templates_and_static_assets_reference_no_external_urls():
    # Só sinaliza atributos/funções que o navegador de fato busca pela rede
    # (src=, href=, url() do CSS, @import) — não pega xmlns="http://.../svg",
    # que é só um identificador de namespace XML, nunca uma requisição.
    padrao_externo = re.compile(
        r"""(?:src|href)\s*=\s*["']https?://|url\(\s*["']?https?://|@import""",
        re.IGNORECASE,
    )
    ofensores = []
    for pasta in (TEMPLATES_DIR, STATIC_DIR):
        for arquivo in pasta.rglob("*"):
            if arquivo.is_file() and arquivo.suffix in {".html", ".css"}:
                conteudo = arquivo.read_text(encoding="utf-8")
                if padrao_externo.search(conteudo):
                    ofensores.append(str(arquivo))
    assert not ofensores, f"Referência de rede externa encontrada em: {ofensores}"


def test_database_url_points_to_local_sqlite_file():
    from app import database

    assert database.DATABASE_URL.startswith("sqlite:///")


def test_startup_initializes_local_sqlite_database_automatically():
    from app import database

    db_path = Path(os.environ["GESTORDECONTRATO_DB_PATH"])
    assert not db_path.exists()

    with TestClient(app):
        pass

    assert db_path.exists()
