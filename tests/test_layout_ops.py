"""Tests for routers/layout_ops.py (the API behind the epvpm CLI).

Uses a temporary config.json, no EPICS needed.
Run from the repo root:  python -m pytest tests/test_layout_ops.py
"""

import json
import multiprocessing
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


# ---------- shared locking in routers/config.py ----------


def _worker(cfg_path, worker_id, n_edits):
    """runs in a separate process, like a second uvicorn worker"""
    config_router.CONFIG_FILE = Path(cfg_path)
    for i in range(n_edits):
        # alternate the two kinds of writer Copilot flagged: an alias update
        # and a layout change, each a full read-modify-write
        with config_router.edit_config() as config:
            config.setdefault("aliases", {})[f"PV{worker_id}:{i}"] = "x"
        with config_router.edit_config() as config:
            layout = layout_ops._default_layout(config)
            layout["livePVNames"].append(f"PV{worker_id}:{i}")


def test_concurrent_writers_in_separate_processes_lose_nothing(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({}))
    workers, n_edits = 4, 25
    ctx = multiprocessing.get_context("fork")
    procs = [
        ctx.Process(target=_worker, args=(str(cfg), w, n_edits)) for w in range(workers)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=60)
        assert p.exitcode == 0
    config = json.loads(cfg.read_text())
    assert len(config["aliases"]) == workers * n_edits
    assert len(config["layouts"]["default"]["livePVNames"]) == workers * n_edits


def test_edit_config_writes_nothing_if_the_block_raises(client):
    client.post("/api/aliases", json={"pv_name": "A", "alias": "I0"})
    with pytest.raises(RuntimeError):
        with config_router.edit_config() as config:
            config["aliases"]["A"] = "changed"
            raise RuntimeError("boom")
    assert client.get("/api/aliases").json() == {"A": "I0"}


def test_missing_config_does_not_mutate_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(config_router, "CONFIG_FILE", tmp_path / "missing.json")
    with config_router.edit_config() as config:
        config["aliases"]["A"] = "I0"
    assert config_router.DEFAULT_CONFIG["aliases"] == {}


# ---------- PV names containing "/" ----------


@pytest.mark.parametrize(
    "set_path, set_body, delete_prefix, get_path",
    [
        ("/api/aliases", {"alias": "I0"}, "/api/aliases/", "/api/aliases"),
        ("/api/egus", {"egu": "V"}, "/api/egus/", "/api/egus"),
        ("/api/value-formats", {"value_format": "exponential"},
         "/api/value-formats/", "/api/value-formats"),
    ],
)
def test_delete_works_for_pv_names_with_slash(
    client, set_path, set_body, delete_prefix, get_path
):
    # The slash arrives decoded even when the client sends %2F (as epvpm
    # does), so the route must use {pv_name:path} to match it
    pv = "BL22:DET/CH1"
    assert client.post(set_path, json={"pv_name": pv, **set_body}).status_code == 200
    assert pv in client.get(get_path).json()
    assert client.delete(delete_prefix + "BL22%3ADET%2FCH1").status_code == 200
    assert pv not in client.get(get_path).json()


def test_live_pv_with_slash_can_be_removed(client):
    pv = "BL22:DET/CH1"
    client.post("/api/layout/live-pvs", json={"pv_names": [pv]})
    assert client.delete("/api/layout/live-pvs/BL22%3ADET%2FCH1").status_code == 200
    assert layout(client)["livePVNames"] == []
