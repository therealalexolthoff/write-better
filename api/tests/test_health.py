from fastapi.testclient import TestClient

from api.app.main import app

client = TestClient(app)


def test_health_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_harness_reports_502_when_unreachable():
    # No harness running in this test, and no network access in CI -
    # this just proves the error path is wired, not a real integration test.
    response = client.get("/health/harness")
    assert response.status_code == 502


def test_page_paths_match_the_web_router():
    """The API serves index.html for each page path (main.PAGES); the web
    app's router (web/src/router.tsx) decides what each one shows. A page
    added to one but not the other would 404 on reload, or show nothing."""
    import re
    from pathlib import Path

    from api.app.main import PAGES

    router = (Path(__file__).resolve().parents[2] / "web" / "src" / "router.tsx").read_text()
    paths_line = next(line for line in router.splitlines() if line.startswith("export const PATHS"))
    web_paths = set(re.findall(r'"(/[^"]*)"', paths_line))
    assert web_paths == {"/", *PAGES}
