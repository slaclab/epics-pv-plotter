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
from routers import energy as energy_router  # noqa: E402
from routers import layout_ops  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    cfg = config_dir / "config.json"
    cfg.write_text(json.dumps({"aliases": {}, "layouts": {"default": {
        "plots": [], "livePVNames": [], "globalTimeWindow": 60}}}))
    monkeypatch.setattr(config_router, "CONFIG_FILE", cfg)
    monkeypatch.setattr(config_router, "LEGACY_CONFIG_FILE", tmp_path / "legacy.json")
    app = FastAPI()
    app.include_router(config_router.router)
    app.include_router(layout_ops.router)
    app.include_router(energy_router.router)
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


def test_version_and_events_track_the_selected_preset(client):
    preset = config_router.CONFIG_FILE.parent / "config1.json"
    preset.write_text(json.dumps({"aliases": {"A": "old"}, "layouts": {"default": {}}}))
    default_version = client.get("/api/config/version").json()
    preset_version = client.get(
        "/api/config/version", params={"config_file": "config1.json"}
    ).json()

    response = client.patch(
        "/api/config-presets/config1.json",
        json={"aliases": {"A": "new"}},
    )

    assert response.status_code == 200
    assert client.get("/api/config/version").json() == default_version
    assert client.get(
        "/api/config/version", params={"config_file": "config1.json"}
    ).json() != preset_version


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


def test_concurrent_writers_in_separate_processes_lose_nothing(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(config_router, "LEGACY_CONFIG_FILE", tmp_path / "legacy.json")
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
    monkeypatch.setattr(config_router, "LEGACY_CONFIG_FILE", tmp_path / "legacy.json")
    with config_router.edit_config() as config:
        config["aliases"]["A"] = "I0"
    assert config_router.DEFAULT_CONFIG["aliases"] == {}


def test_config_presets_can_be_listed_and_loaded_without_changing_default(client):
    preset = config_router.CONFIG_FILE.parent / "config1.json"
    preset.write_text(json.dumps({
        "layouts": {
            "default": {
                "plots": [{"id": 2, "pvNames": ["PRESET:PV"]}],
                "livePVNames": [],
                "globalTimeWindow": 120,
            }
        }
    }))

    response = client.get("/api/config-presets")
    assert response.status_code == 200
    assert response.json()["files"] == ["config.json", "config1.json"]

    response = client.get("/api/config-presets/config1.json")
    assert response.status_code == 200
    assert response.json()["layouts"]["default"]["plots"][0]["pvNames"] == [
        "PRESET:PV"
    ]
    assert client.get("/api/config").json()["layouts"]["default"]["plots"] == []


def test_missing_config_preset_returns_404(client):
    assert client.get("/api/config-presets/not-found.json").status_code == 404


def test_named_config_preset_can_be_created_as_a_copy(client):
    preset = config_router.CONFIG_FILE.parent / "config1.json"
    preset.write_text(json.dumps({
        "aliases": {"A": "I0"},
        "layouts": {"default": {"plots": [{"id": 1, "pvNames": ["A"]}]}},
    }))

    response = client.post(
        "/api/config-presets/config3.json",
        params={"source": "config1.json"},
    )

    assert response.status_code == 200
    assert response.json()["filename"] == "config3.json"
    copied = json.loads(
        (config_router.CONFIG_FILE.parent / "config3.json").read_text()
    )
    assert copied["aliases"] == {"A": "I0"}
    assert copied["layouts"]["default"]["plots"][0]["pvNames"] == ["A"]


def test_fresh_install_creates_default_preset(tmp_path, monkeypatch):
    config_dir = tmp_path / "configs"
    monkeypatch.setattr(config_router, "CONFIG_FILE", config_dir / "config.json")
    monkeypatch.setattr(config_router, "LEGACY_CONFIG_FILE", tmp_path / "missing.json")
    app = FastAPI()
    app.include_router(config_router.router)
    client = TestClient(app)

    response = client.get("/api/config-presets")

    assert response.status_code == 200
    assert response.json()["files"] == ["config.json"]
    response = client.get("/api/config-presets/config.json")

    assert response.status_code == 200
    assert response.json() == config_router.DEFAULT_CONFIG
    assert (config_dir / "config.json").is_file()


def test_missing_default_is_initialized_and_migrates_legacy_config(tmp_path, monkeypatch):
    config_dir = tmp_path / "configs"
    legacy_file = tmp_path / "config.json"
    config_dir.mkdir()
    legacy = {"aliases": {"OLD:PV": "Legacy"}, "layouts": {"default": {"plots": []}}}
    legacy_file.write_text(json.dumps(legacy))
    monkeypatch.setattr(config_router, "CONFIG_FILE", config_dir / "config.json")
    monkeypatch.setattr(config_router, "LEGACY_CONFIG_FILE", legacy_file)
    app = FastAPI()
    app.include_router(config_router.router)
    client = TestClient(app)

    response = client.get("/api/config-presets/config.json")

    assert response.status_code == 200
    assert response.json() == legacy
    assert json.loads((config_dir / "config.json").read_text()) == legacy
    assert json.loads(legacy_file.read_text()) == legacy


def test_existing_default_is_not_overwritten_by_legacy_file(tmp_path, monkeypatch):
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    current = {"aliases": {"NEW:PV": "Current"}}
    legacy = {"aliases": {"OLD:PV": "Legacy"}}
    default_file = config_dir / "config.json"
    default_file.write_text(json.dumps(current))
    legacy_file = tmp_path / "config.json"
    legacy_file.write_text(json.dumps(legacy))
    monkeypatch.setattr(config_router, "CONFIG_FILE", default_file)
    monkeypatch.setattr(config_router, "LEGACY_CONFIG_FILE", legacy_file)

    config_router._ensure_default_config_file()

    assert json.loads(default_file.read_text()) == current
    assert json.loads(legacy_file.read_text()) == legacy


def test_preset_updates_only_requested_sections(client):
    preset = config_router.CONFIG_FILE.parent / "config1.json"
    preset.write_text(json.dumps({
        "aliases": {"A": "old"},
        "layouts": {"default": {"plots": [{"id": 1, "pvNames": ["A"]}]}},
    }))

    response = client.patch(
        "/api/config-presets/config1.json",
        json={"aliases": {"A": "new"}, "egus": {"A": "V"}},
    )
    assert response.status_code == 200
    preset_config = client.get("/api/config-presets/config1.json").json()
    assert preset_config["aliases"] == {"A": "new"}
    assert preset_config["egus"] == {"A": "V"}
    assert preset_config["layouts"]["default"]["plots"][0]["pvNames"] == ["A"]
    assert client.get("/api/config").json()["layouts"]["default"]["plots"] == []


def test_preset_patch_merges_individual_entries_and_deletes_explicitly(client):
    preset = config_router.CONFIG_FILE.parent / "config1.json"
    preset.write_text(json.dumps({"aliases": {"A": "old", "B": "keep"}}))

    response = client.patch(
        "/api/config-presets/config1.json",
        json={"aliases": {"A": "new", "C": "concurrent"}},
    )

    assert response.status_code == 200
    assert client.get("/api/config-presets/config1.json").json()["aliases"] == {
        "A": "new",
        "B": "keep",
        "C": "concurrent",
    }
    response = client.patch(
        "/api/config-presets/config1.json",
        json={"aliases": {"B": None}},
    )
    assert response.status_code == 200
    assert client.get("/api/config-presets/config1.json").json()["aliases"] == {
        "A": "new",
        "C": "concurrent",
    }


@pytest.mark.parametrize(
    "updates",
    [
        {"aliases": {"PV": {"bad": 1}}},
        {"thresholds": {"PV": {"upper": "not-a-number"}}},
        {"thresholds": {"PV": {"upper": 10**1000}}},
        {"thresholds": {"PV": {"upper": 2, "lower": 3}}},
        {"value_formats": {"PV": "unsupported"}},
        {"layouts": {"default": {"plots": [{"pvNames": "not-a-list"}]}}},
    ],
)
def test_preset_patch_rejects_invalid_nested_entries_without_writing(client, updates):
    preset = config_router.CONFIG_FILE.parent / "config1.json"
    original = {"aliases": {"PV": "safe"}}
    preset.write_text(json.dumps(original))

    response = client.patch("/api/config-presets/config1.json", json=updates)

    assert response.status_code == 422
    assert client.get("/api/config-presets/config1.json").json() == original


def test_preset_path_does_not_follow_symlinks_outside_config_directory(
    client, tmp_path
):
    outside = tmp_path / "outside.json"
    outside.write_text("{}")
    (config_router.CONFIG_FILE.parent / "outside-link.json").symlink_to(outside)

    response = client.get("/api/config-presets/outside-link.json")

    assert response.status_code == 404


def test_preset_updates_reject_unknown_sections(client):
    (config_router.CONFIG_FILE.parent / "config1.json").write_text("{}")
    response = client.patch(
        "/api/config-presets/config1.json",
        json={"unexpected": {}},
    )
    assert response.status_code == 422


def test_energy_config_reads_from_requested_preset(client):
    preset = config_router.CONFIG_FILE.parent / "config1.json"
    preset.write_text(json.dumps({
        "energy": {
            "encoder_pv": "BL22:TEST:ENCODER.REP",
            "d_spacing_pv": "BL22:TEST:D",
            "offset_pv": "BL22:TEST:OFFSET",
        }
    }))

    response = client.get(
        "/api/energy-config", params={"config_file": "config1.json"}
    )
    assert response.status_code == 200
    assert response.json()["encoder_pv"] == "BL22:TEST:ENCODER.REP"

    response = client.post(
        "/api/energy-config",
        params={"config_file": "config1.json"},
        json={
            "encoder_pv": "BL22:TEST:NEW_ENCODER",
            "d_spacing_pv": "BL22:TEST:D2",
            "offset_pv": "BL22:TEST:OFFSET2",
        },
    )
    assert response.status_code == 200
    assert response.json()["energy"]["encoder_pv"] == "BL22:TEST:NEW_ENCODER.REP"
    assert client.get(
        "/api/energy-config", params={"config_file": "config1.json"}
    ).json()["d_spacing_pv"] == "BL22:TEST:D2"
    assert client.get("/api/energy-config").json()["encoder_pv"] != (
        "BL22:TEST:NEW_ENCODER.REP"
    )


def test_invalid_named_energy_config_fails_instead_of_using_defaults(client):
    (config_router.CONFIG_FILE.parent / "invalid.json").write_text("{")

    response = client.get(
        "/api/energy-config", params={"config_file": "invalid.json"}
    )

    assert response.status_code == 500
    assert "invalid JSON" in response.json()["detail"]


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
