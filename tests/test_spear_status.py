import io
import json
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from routers import spear_status  # noqa: E402


def test_spear_messages_endpoint_returns_messages(monkeypatch):
    payload = {
        "TIME": "23-Nov-2026 15:32:43",
        "messages": [
            {"activationDate": "Nov 23, 2026", "message": "Beam current stable"}
        ]
    }
    monkeypatch.setattr(
        spear_status,
        "urlopen",
        lambda url, timeout: io.BytesIO(json.dumps(payload).encode()),
    )
    app = FastAPI()
    app.include_router(spear_status.router)

    response = TestClient(app).get("/api/spear-messages")

    assert response.status_code == 200
    assert response.json() == payload


def test_spear_messages_endpoint_rejects_invalid_upstream_messages(monkeypatch):
    payload = {
        "TIME": "23-Nov-2026 15:32:43",
        "messages": [{"message": "Missing activation date"}],
    }
    monkeypatch.setattr(
        spear_status,
        "urlopen",
        lambda url, timeout: io.BytesIO(json.dumps(payload).encode()),
    )
    app = FastAPI()
    app.include_router(spear_status.router)

    response = TestClient(app).get("/api/spear-messages")

    assert response.status_code == 502
    assert response.json()["detail"] == "SPEAR status endpoint returned invalid messages"
