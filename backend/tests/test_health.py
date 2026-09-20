def test_health_says_ok(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "schema_version": "1.0"}


def test_opening_the_site_gives_the_page_or_the_docs(client):
    """In a container the built page is served from / (one origin). In development the
    page is on :5173, so / is a shortcut to the API's own documentation."""
    from app.web import BUILT_PAGE

    response = client.get("/", follow_redirects=False)
    if (BUILT_PAGE / "index.html").is_file():
        assert response.status_code == 200 and "<title>DiaCausal" in response.text
    else:
        assert response.status_code == 307 and response.headers["location"] == "/docs"


def test_every_reply_carries_the_security_headers(client):
    headers = client.get("/api/health").headers

    assert "frame-ancestors 'none'" in headers["content-security-policy"]
    assert "default-src 'self'" in headers["content-security-policy"]
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["referrer-policy"] == "no-referrer"
    assert "microphone=(self)" in headers["permissions-policy"]  # the voice button needs it


def test_no_hsts_in_development(client):
    """Telling a browser to refuse http for a year is a production-only promise."""
    assert "strict-transport-security" not in client.get("/api/health").headers


def test_in_production_the_api_docs_are_off_and_hsts_is_sent(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import create_app
    from conftest import BASE_URL, TEST_DB

    monkeypatch.setenv("DIACAUSAL_ENV", "production")
    production = TestClient(create_app(TEST_DB), base_url=BASE_URL)

    assert production.get("/docs").status_code == 404
    assert production.get("/openapi.json").status_code == 404
    headers = production.get("/api/health").headers
    assert headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"


def test_a_body_larger_than_the_limit_is_refused_before_it_is_read(client):
    from app.settings import MAX_REQUEST_BYTES

    reply = client.post(
        "/api/v1/chat",
        content=b"x" * 32,  # the header is what is checked, so nothing huge is sent here
        headers={"Content-Type": "application/json", "Content-Length": str(MAX_REQUEST_BYTES + 1)},
    )
    assert reply.status_code == 413
