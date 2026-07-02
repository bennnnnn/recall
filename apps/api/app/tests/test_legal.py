from fastapi.testclient import TestClient

from app.main import create_app


def test_privacy_policy_html() -> None:
    client = TestClient(create_app())
    response = client.get("/legal/privacy")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Privacy Policy" in response.text
    assert response.headers.get("cache-control") == "public, max-age=3600"


def test_terms_of_service_html() -> None:
    client = TestClient(create_app())
    response = client.get("/legal/terms")
    assert response.status_code == 200
    assert "Terms of Service" in response.text
