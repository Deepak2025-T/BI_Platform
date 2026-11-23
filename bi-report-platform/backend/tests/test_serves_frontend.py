"""
Serving the built app from the API itself, for a server with nothing in front of it.

With nginx in front this never runs - nginx serves frontend/dist and the API only ever sees /api.
Without it, one process on one port has to do both, and the two things that go wrong are a deep
link 404ing and a mistyped API path answering with a page.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import FRONTEND_DIR, app

built = pytest.mark.skipif(not (FRONTEND_DIR / "index.html").is_file(),
                           reason="the frontend has not been built (npm run build)")

client = TestClient(app)


def test_the_api_still_answers_first():
    """The catch-all is registered last so it can never shadow a real endpoint."""
    assert client.get("/api/health").json() == {"status": "ok"}


@built
def test_the_root_is_the_app():
    page = client.get("/")
    assert page.status_code == 200
    assert "<title>ReportsAI</title>" in page.text


@built
def test_a_deep_link_is_the_app_not_a_404():
    """Opening or reloading /reports/114 has to work: it is a route inside the app, and only the
    browser knows that - the server has never heard of it."""
    page = client.get("/reports/114")
    assert page.status_code == 200
    assert "<title>ReportsAI</title>" in page.text


@built
def test_index_is_not_cached():
    """The asset filenames carry a content hash, so they may be kept; index.html is what points at
    them, and a cached copy of it keeps a browser on yesterday's bundle after a deploy."""
    assert "no-cache" in client.get("/").headers.get("cache-control", "")


@built
def test_a_real_file_is_served_as_itself():
    assert client.get("/favicon.png").status_code == 200
    assert client.get("/timus-logo.png").headers["content-type"] == "image/png"


@built
def test_a_mistyped_api_path_is_a_404_not_a_page():
    """Answering /api/helth with HTML would have the client parsing a document as JSON, and the
    error it reports then has nothing to do with the mistake that caused it."""
    missing = client.get("/api/helth")
    assert missing.status_code == 404
    assert "html" not in missing.headers.get("content-type", "")


@built
def test_a_path_cannot_climb_out_of_the_build_directory():
    """`/../backend/.env` must be the app, not a file. Nothing outside dist is ours to serve."""
    for attempt in ["../backend/.env", "../../backend/.env", "..%2f..%2fbackend%2f.env"]:
        answer = client.get(f"/{attempt}")
        assert answer.status_code in (200, 404), attempt
        assert "JWT_SECRET" not in answer.text, f"{attempt} escaped the build directory"
