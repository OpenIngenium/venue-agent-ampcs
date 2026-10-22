import pytest
from fastapi.testclient import TestClient

from main import app
client_no_auth = TestClient(app)

def test_health_success():
    """Nominal health check – should return 200 and a known status enum."""

    resp = client_no_auth.get("/api/v3/health")
    assert resp.status_code == 200, f"Unexpected status: {resp.status_code}"
    data = resp.json()
    assert "status" in data, "Missing 'status' field"
    assert data["status"] in ("OK", "ERROR", "UNKNOWN")
    assert "message" in data, "Missing 'message' field"

def test_health_invalid_method():
    """Off‑nominal: POST is not allowed on the health endpoint (expects 405)."""
    resp = client_no_auth.post("/api/v3/health")
    assert resp.status_code == 405, f"Expected 405, got {resp.status_code}"

def test_health_invalid_method_patch():
    """Off‑nominal: POST is not allowed on the health endpoint (expects 405)."""
    resp = client_no_auth.patch("/api/v3/health")
    assert resp.status_code == 405, f"Expected 405, got {resp.status_code}"

def test_health_invalid_method_delete():
    """Off‑nominal: POST is not allowed on the health endpoint (expects 405)."""
    resp = client_no_auth.delete("/api/v3/health")
    assert resp.status_code == 405, f"Expected 405, got {resp.status_code}"