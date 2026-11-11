"""Tests for routers/layout_ops.py (the API behind the epvpm CLI).

Uses a temporary config.json, no EPICS needed.
Run from the repo root:  python -m pytest tests/test_layout_ops.py
"""

import json
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from routers import config as config_router  # noqa: E402
from routers import layout_ops  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"aliases": {}, "layouts": {"default": {
        "plots": [], "livePVNames": [], "globalTimeWindow": 60}}}))
    monkeypatch.setattr(config_router, "CONFIG_FILE", cfg)
    monkeypatch.setattr(layout_ops, "LOCK_FILE", tmp_path / "config.json.lock")
    app = FastAPI()
    app.include_router(config_router.router)
    app.include_router(layout_ops.router)
    return TestClient(app)


def layout(client):
    return client.get("/api/layout").json()


def test_add_plots_fill_grid_like_the_ui(client):
    for pv in ("A", "B", "C", "D"):
        assert client.post("/api/layout/plots", json={"pv_names": [pv]}).status_code == 200
    plots = layout(client)["plots"]
    assert [(p["id"], p["x"], p["y"], p["w"], p["h"]) for p in plots] == [
        (1, 0, 0, 4, 3), (2, 4, 0, 4, 3), (3, 8, 0, 4, 3), (4, 0, 3, 4, 3)]


def test_add_plot_dedupes_and_rejects_empty(client):
    r = client.post("/api/layout/plots", json={"pv_names": [" A ", "A", "B"], "width": 2})
    assert r.json()["plot"]["pvNames"] == ["A", "B"]
    assert r.json()["plot"]["w"] == 8
    assert client.post("/api/layout/plots", json={"pv_names": ["  "]}).status_code == 422
    assert client.post("/api/layout/plots", json={"pv_names": []}).status_code == 422


def test_remove_plot_repacks(client):
    for pv in ("A", "B", "C", "D"):
        client.post("/api/layout/plots", json={"pv_names": [pv]})
    assert client.delete("/api/layout/plots/2").status_code == 200
    plots = layout(client)["plots"]
    assert [(p["id"], p["x"], p["y"]) for p in plots] == [(1, 0, 0), (3, 4, 0), (4, 8, 0)]
    assert client.delete("/api/layout/plots/99").status_code == 404


def test_plot_pvs_add_and_remove(client):
    client.post("/api/layout/plots", json={"pv_names": ["A"]})
    r = client.post("/api/layout/plots/1/pvs", json={"pv_names": ["B", "A"]})
    assert r.json()["plot"]["pvNames"] == ["A", "B"]
    assert client.delete("/api/layout/plots/1/pvs/B").json()["plot_removed"] is False
    assert client.delete("/api/layout/plots/1/pvs/B").status_code == 404
    assert client.delete("/api/layout/plots/1/pvs/A").json()["plot_removed"] is True
    assert layout(client)["plots"] == []


def test_live_pvs(client):
    client.post("/api/layout/live-pvs", json={"pv_names": ["X:Y", "X:Z"]})
    client.post("/api/layout/live-pvs", json={"pv_names": ["X:Y"]})
    assert layout(client)["livePVNames"] == ["X:Y", "X:Z"]
    assert client.delete("/api/layout/live-pvs/X%3AY").status_code == 200
    assert layout(client)["livePVNames"] == ["X:Z"]
    assert client.delete("/api/layout/live-pvs/X%3AY").status_code == 404


def test_version_separates_layout_and_settings(client):
    v0 = client.get("/api/config/version").json()
    client.post("/api/aliases", json={"pv_name": "A", "alias": "I0"})
    v1 = client.get("/api/config/version").json()
    assert v1["layout"] == v0["layout"] and v1["settings"] != v0["settings"]
    client.post("/api/layout/live-pvs", json={"pv_names": ["A"]})
    v2 = client.get("/api/config/version").json()
    assert v2["layout"] != v1["layout"] and v2["settings"] == v1["settings"]


def test_other_config_sections_preserved(client):
    client.post("/api/aliases", json={"pv_name": "A", "alias": "I0"})
    client.post("/api/layout/plots", json={"pv_names": ["A"]})
    client.delete("/api/layout/plots/1")
    assert client.get("/api/aliases").json() == {"A": "I0"}
