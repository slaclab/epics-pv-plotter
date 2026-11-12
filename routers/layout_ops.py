# routers/layout_ops.py
"""
Fine-grained layout editing API - add/remove single plots and Live PVs.

Used by the `epvpm` command-line tool (scripts/epvpm) so staff can edit the
shared layout without opening a browser on the Pi. Each endpoint changes only
the part it names, under a file lock, so two people editing at once don't
overwrite each other (unlike POST /api/layout, which replaces the whole
layout). Locking is shared with every other config writer via
routers.config.edit_config().

GET /api/config/events pushes a message to open browsers whenever
config.json changes, so they reload right away (GET /api/config/version
returns the same fingerprints on demand).

Plot placement mirrors src/stores/usePlotStore.js (findBestPosition /
repackPlots) so plots added here land where the UI would put them.
"""

import asyncio
import copy
import hashlib
import json
from typing import List

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from routers import config as config_module
from routers.config import DEFAULT_CONFIG, edit_config, load_config

router = APIRouter(prefix="/api", tags=["layout-ops"])

# Keep in sync with PLOT_CONFIG in src/utils/constants.js
GRID_COLS = 12
DEFAULT_WIDTH = 4
DEFAULT_HEIGHT = 3

# How often the events stream looks at config.json's modification time
# (a local file stat, no network traffic) and how often it sends a
# keep-alive comment so idle connections aren't dropped by proxies
WATCH_INTERVAL_S = 1.0
KEEPALIVE_S = 15.0

# Top-level config keys that are not the layout (shown by the browser
# outside the plot grid: aliases, EGUs, thresholds, value formats, energy)
LAYOUT_KEY = "layouts"


def _default_layout(config: dict) -> dict:
    layouts = config.setdefault(LAYOUT_KEY, {})
    layout = layouts.setdefault(
        "default", copy.deepcopy(DEFAULT_CONFIG[LAYOUT_KEY]["default"])
    )
    layout.setdefault("plots", [])
    layout.setdefault("livePVNames", [])
    return layout


def _normalize_names(names: List[str]) -> List[str]:
    """strip, drop empties, de-duplicate keeping order"""
    seen: dict = {}
    for name in names:
        name = name.strip()
        if name:
            seen.setdefault(name, None)
    return list(seen)


# ---------- grid placement (port of usePlotStore.js) ----------


def _overlaps(x1, y1, w1, h1, x2, y2, w2, h2) -> bool:
    return not (x1 + w1 <= x2 or x2 + w2 <= x1 or y1 + h1 <= y2 or y2 + h2 <= y1)


def find_best_position(existing: List[dict], width: int, height: int) -> dict:
    """first free slot scanning rows top-to-bottom, columns left-to-right"""
    if not existing:
        return {"x": 0, "y": 0}
    row = 0
    while row <= 100:
        for col in range(0, GRID_COLS - width + 1):
            if not any(
                _overlaps(col, row, width, height, p["x"], p["y"], p["w"], p["h"])
                for p in existing
            ):
                return {"x": col, "y": row}
        row += DEFAULT_HEIGHT
    return {"x": 0, "y": row}


def repack_plots(plots: List[dict]) -> List[dict]:
    """re-place plots in reading order so removing one leaves no gap"""
    placed: List[dict] = []
    for plot in sorted(plots, key=lambda p: (p["y"], p["x"])):
        placed.append({**plot, **find_best_position(placed, plot["w"], plot["h"])})
    positions = {p["id"]: (p["x"], p["y"]) for p in placed}
    return [{**p, "x": positions[p["id"]][0], "y": positions[p["id"]][1]} for p in plots]


def _find_plot(layout: dict, plot_id: int) -> dict:
    for plot in layout["plots"]:
        if plot.get("id") == plot_id:
            return plot
    raise HTTPException(status_code=404, detail=f"Plot {plot_id} not found")


# ---------- change detection for open browsers ----------


def _digest(value) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:16]


def config_version() -> dict:
    """
    Hashes of the layout and of everything else, so a browser can reload
    only the part that changed (a new alias must not discard unsaved plot
    edits in someone else's browser).
    """
    config = load_config()
    layout = config.get(LAYOUT_KEY, {}).get("default", {})
    settings = {k: v for k, v in config.items() if k != LAYOUT_KEY}
    return {"layout": _digest(layout), "settings": _digest(settings)}


def _config_mtime():
    try:
        return config_module.CONFIG_FILE.stat().st_mtime_ns
    except FileNotFoundError:
        return None


@router.get("/config/version")
async def get_config_version():
    return config_version()


@router.get("/config/events")
async def config_events(request: Request):
    """
    Server-Sent Events stream: sends the current version on connect, then a
    new one each time config.json changes (from the UI, epvpm, or a manual
    edit). Watching the file rather than hooking save_config also works with
    several uvicorn workers.
    """

    async def stream():
        last_mtime = object()  # forces a first message
        last_version = None
        idle = 0.0
        while not await request.is_disconnected():
            mtime = _config_mtime()
            if mtime != last_mtime:
                last_mtime = mtime
                version = config_version()
                if version != last_version:
                    last_version = version
                    idle = 0.0
                    yield f"data: {json.dumps(version)}\n\n"
            if idle >= KEEPALIVE_S:
                idle = 0.0
                yield ": keep-alive\n\n"
            await asyncio.sleep(WATCH_INTERVAL_S)
            idle += WATCH_INTERVAL_S

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        # X-Accel-Buffering: stop nginx from holding events back
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------- plots ----------


class PlotAdd(BaseModel):
    pv_names: List[str] = Field(min_length=1)
    # Size in units of the default plot size, like the UI's size selector
    width: int = Field(default=1, ge=1, le=GRID_COLS // DEFAULT_WIDTH)
    height: int = Field(default=1, ge=1, le=2)


@router.post("/layout/plots")
async def add_plot(req: PlotAdd):
    """add one plot showing the given PV(s); returns the new plot"""
    pv_names = _normalize_names(req.pv_names)
    if not pv_names:
        raise HTTPException(status_code=422, detail="At least one PV name is required")
    w, h = DEFAULT_WIDTH * req.width, DEFAULT_HEIGHT * req.height
    with edit_config() as config:
        layout = _default_layout(config)
        plots = layout["plots"]
        plot = {
            "id": max((p.get("id", 0) for p in plots), default=0) + 1,
            "pvNames": pv_names,
            **find_best_position(plots, w, h),
            "w": w,
            "h": h,
        }
        plots.append(plot)
    return {"status": "ok", "plot": plot}


@router.delete("/layout/plots/{plot_id}")
async def remove_plot(plot_id: int):
    """remove a whole plot and close the gap it leaves"""
    with edit_config() as config:
        layout = _default_layout(config)
        plot = _find_plot(layout, plot_id)
        layout["plots"] = repack_plots([p for p in layout["plots"] if p is not plot])
    return {"status": "ok", "removed": plot}


class PlotPVs(BaseModel):
    pv_names: List[str] = Field(min_length=1)


@router.post("/layout/plots/{plot_id}/pvs")
async def add_pvs_to_plot(plot_id: int, req: PlotPVs):
    """add PV traces to an existing plot"""
    with edit_config() as config:
        plot = _find_plot(_default_layout(config), plot_id)
        plot["pvNames"] = _normalize_names(plot.get("pvNames", []) + req.pv_names)
    return {"status": "ok", "plot": plot}


@router.delete("/layout/plots/{plot_id}/pvs/{pv_name:path}")
async def remove_pv_from_plot(plot_id: int, pv_name: str):
    """remove one PV trace; a plot left with no PVs is removed entirely"""
    with edit_config() as config:
        layout = _default_layout(config)
        plot = _find_plot(layout, plot_id)
        if pv_name not in plot.get("pvNames", []):
            raise HTTPException(
                status_code=404, detail=f"{pv_name} is not in plot {plot_id}"
            )
        plot["pvNames"] = [n for n in plot["pvNames"] if n != pv_name]
        plot_removed = not plot["pvNames"]
        if plot_removed:
            layout["plots"] = repack_plots([p for p in layout["plots"] if p is not plot])
    return {"status": "ok", "plot_removed": plot_removed}


# ---------- Live PV Values list ----------


@router.post("/layout/live-pvs")
async def add_live_pvs(req: PlotPVs):
    """append PVs to the Live PV Values list (duplicates are ignored)"""
    with edit_config() as config:
        layout = _default_layout(config)
        layout["livePVNames"] = _normalize_names(layout["livePVNames"] + req.pv_names)
    return {"status": "ok", "livePVNames": layout["livePVNames"]}


@router.delete("/layout/live-pvs/{pv_name:path}")
async def remove_live_pv(pv_name: str):
    """remove one PV from the Live PV Values list"""
    with edit_config() as config:
        layout = _default_layout(config)
        if pv_name not in layout["livePVNames"]:
            raise HTTPException(
                status_code=404, detail=f"{pv_name} is not in the Live PV list"
            )
        layout["livePVNames"] = [n for n in layout["livePVNames"] if n != pv_name]
    return {"status": "ok", "livePVNames": layout["livePVNames"]}
