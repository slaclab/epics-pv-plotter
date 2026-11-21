# routers/config.py
"""
Configuration API router - handles shared aliases and layouts.
The active configuration is stored in configs/config.json.
"""

import copy
import errno
import fcntl
import json
import logging
import re
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Any, Iterator, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

log = logging.getLogger(__name__)

# create router, setup prefix and tags
router = APIRouter(prefix="/api", tags=["config"])

# set up the files' path and file name
CONFIG_FILE = Path(__file__).parent.parent / "configs" / "config.json"

DEFAULT_CONFIG = {
    "aliases": {},
    "layouts": {
        "default": {
            "plots": [],
            "livePVNames": [],
            "globalTimeWindow": 60,
            "showBeamlineStatus": False,
        }
    },
}


def _ensure_config_path(config_file: Path) -> Path:
    config_dir = CONFIG_FILE.parent.resolve()
    resolved = config_file.resolve()
    if resolved.parent != config_dir:
        raise HTTPException(status_code=400, detail="Invalid configuration path")
    return resolved


def load_config(config_file: Path | None = None) -> dict:
    config_file = _ensure_config_path(config_file or CONFIG_FILE)
    # deepcopy: callers mutate the result, which must not change the defaults
    if not config_file.exists():
        return copy.deepcopy(DEFAULT_CONFIG)
    try:
        # open config file and load the json data
        with open(config_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        log.warning(f"Failed to read config, using default: {e}")
        return copy.deepcopy(DEFAULT_CONFIG)


def save_config(config: dict, config_file: Path | None = None) -> None:
    config_file = _ensure_config_path(config_file or CONFIG_FILE)
    config_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = config_file.with_suffix(".json.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        try:
            tmp.replace(config_file)   # replace the old configuration file
        except OSError as e:
            if e.errno != errno.EBUSY:
                raise
            # A directly bind-mounted config file can't be atomically replaced
            # via rename, so write in place instead.
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            tmp.unlink(missing_ok=True)
    except IOError as e:
        log.error(f"Failed to save config: {e}")
        raise HTTPException(status_code=500, detail="Failed to save config")


@contextmanager
def config_lock(config_file: Path | None = None) -> Iterator[None]:
    config_file = _ensure_config_path(config_file or CONFIG_FILE)
    """
    Exclusive lock on config.json across processes (e.g. several uvicorn
    workers). Every writer must hold it for its whole read-modify-write so
    one request can't save a stale copy over another's change.

    Never `await` while holding it: the flock call blocks, and a second
    coroutine in the same process waiting on it would stall the event loop.
    """
    config_file = config_file or CONFIG_FILE
    lock_path = config_file.with_suffix(".json.lock")
    config_file.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


@contextmanager
def edit_config(
    config_file: Path | None = None, *, strict: bool = False
) -> Iterator[dict]:
    """
    Locked read-modify-write of config.json:

        with edit_config() as config:
            config["aliases"][pv] = alias

    The config is saved when the block ends normally; if the block raises
    (e.g. HTTPException), nothing is written.
    """
    config_file = _ensure_config_path(config_file or CONFIG_FILE)
    with config_lock(config_file):
        if strict:
            config = _read_config_file(config_file)
        else:
            config = load_config(config_file)
        yield config
        save_config(config, config_file)


# ---------- complete setup of the router ----------

@router.get("/config")
async def get_config():
    """get the complete configuration"""
    return load_config()

_SAFE_CONFIG_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.json$")


    # Accept only simple preset basenames (no path separators), ending in .json.
    # This prevents path traversal and absolute path injection before filesystem use.
    if not re.fullmatch(r"[A-Za-z0-9_.-]+\.json", filename):
        raise HTTPException(status_code=400, detail="Invalid configuration filename")

    candidate = Path(filename).name
    if not _SAFE_CONFIG_FILENAME.fullmatch(filename):
    preset_path = (config_dir / candidate).resolve()

    candidate = Path(filename)
    if candidate.name != filename or candidate.suffix != ".json":
        raise HTTPException(status_code=400, detail="Invalid configuration filename")

    config_dir = CONFIG_FILE.parent.resolve()
    preset_path = (config_dir / candidate.name).resolve()
    if preset_path.parent != config_dir:
        raise HTTPException(status_code=400, detail="Invalid configuration path")
    if not preset_path.is_file():
        raise HTTPException(status_code=404, detail="Configuration not found")
    return preset_path


def _read_config_file(config_file: Path) -> dict:
    config_file = _ensure_config_path(config_file)
    try:
        with config_file.open("r", encoding="utf-8") as source:
            config = json.load(source)
    except json.JSONDecodeError as error:
        log.error("Invalid JSON in configuration %s: %s", config_file.name, error)
        raise HTTPException(
            status_code=500,
            detail=f"Configuration {config_file.name} contains invalid JSON",
        ) from error
    except OSError as error:
        log.error("Failed to read configuration %s: %s", config_file.name, error)
        raise HTTPException(
            status_code=500, detail=f"Failed to read configuration {config_file.name}"
        ) from error
    if not isinstance(config, dict):
        raise HTTPException(
            status_code=500,
            detail=f"Configuration {config_file.name} must contain a JSON object",
        )
    return config


def resolve_config_file(filename: str | None = None) -> Path:
    return CONFIG_FILE if filename is None else _preset_path(filename)


@router.get("/config-presets")
async def list_config_presets():
    """list JSON configuration files available in the configs directory"""
    config_dir = CONFIG_FILE.parent
    if not config_dir.exists():
        return {"files": []}

    files = []
    for path in sorted(config_dir.glob("*.json")):
        if path.is_file() and path.resolve().parent == config_dir.resolve():
            files.append(path.name)
    return {"files": files}


@router.get("/config-presets/{filename}")
async def get_config_preset(filename: str):
    """read a named configuration preset without changing the active config"""
    return _read_config_file(_preset_path(filename))


@router.patch("/config-presets/{filename}")
async def update_config_preset(filename: str, updates: Dict[str, Any]):
    """update selected configuration sections without replacing other sections"""
    allowed_sections = {
        "aliases",
        "egus",
        "thresholds",
        "value_formats",
        "layouts",
    }
    if not updates or updates.keys() - allowed_sections:
        raise HTTPException(status_code=422, detail="Invalid configuration sections")
    if any(not isinstance(value, dict) for value in updates.values()):
        raise HTTPException(
            status_code=422, detail="Configuration sections must be JSON objects"
        )

    preset_path = _preset_path(filename)
    with edit_config(preset_path, strict=True) as config:
        for section, values in updates.items():
            if section == "layouts":
                layouts = config.get("layouts")
                if not isinstance(layouts, dict):
                    layouts = {}
                    config["layouts"] = layouts
                layouts.update(values)
            else:
                config[section] = values
    return {"status": "ok"}


@router.post("/config")
async def update_config(config: Dict[str, Any]):
    """save the configuration"""
    with config_lock():
        save_config(config)
    return {"status": "ok"}


# ----------alias ----------

@router.get("/aliases")
async def get_aliases():
    """get all the alias projections"""
    return load_config().get("aliases", {})


class AliasUpdate(BaseModel):
    pv_name: str
    alias: str


@router.post("/aliases")
async def set_alias(update: AliasUpdate):
    """set/update single  PV alias"""
    with edit_config() as config:
        config.setdefault("aliases", {})
        config["aliases"][update.pv_name] = update.alias
    return {"status": "ok", "aliases": config["aliases"]}


@router.delete("/aliases/{pv_name:path}")
async def delete_alias(pv_name: str):
    """ remove a certain PV's alias """
    with edit_config() as config:
        config.get("aliases", {}).pop(pv_name, None)
    return {"status": "ok"}

@router.get("/egus")
async def get_egus():
    """get all EGU settings"""
    return load_config().get("egus", {})


class EguUpdate(BaseModel):
    pv_name: str
    egu: str


@router.post("/egus")
async def set_egu(update: EguUpdate):
    """set/update a single PV's EGU"""
    with edit_config() as config:
        config.setdefault("egus", {})
        config["egus"][update.pv_name] = update.egu
    return {"status": "ok", "egus": config["egus"]}


@router.delete("/egus/{pv_name:path}")
async def delete_egu(pv_name: str):
    """remove a certain PV's EGU (back to the default)"""
    with edit_config() as config:
        config.get("egus", {}).pop(pv_name, None)
    return {"status": "ok"}


# ---------- value formats ("regular" / "exponential") ----------

@router.get("/value-formats")
async def get_value_formats():
    """get all value format settings"""
    return load_config().get("value_formats", {})


class ValueFormatUpdate(BaseModel):
    pv_name: str
    value_format: Literal["regular", "exponential"]


@router.post("/value-formats")
async def set_value_format(update: ValueFormatUpdate):
    """set/update a single PV's value format"""
    with edit_config() as config:
        config.setdefault("value_formats", {})
        config["value_formats"][update.pv_name] = update.value_format
    return {"status": "ok", "value_formats": config["value_formats"]}


@router.delete("/value-formats/{pv_name:path}")
async def delete_value_format(pv_name: str):
    """remove a certain PV's value format (back to regular)"""
    with edit_config() as config:
        config.get("value_formats", {}).pop(pv_name, None)
    return {"status": "ok"}


class LayoutUpdate(BaseModel):
    plots: list
    livePVNames: list
    globalTimeWindow: int
    # Older clients don't send it; default keeps the table hidden
    showBeamlineStatus: bool = False


@router.get("/layout")
async def get_layout():
    return load_config().get("layouts", {}).get("default", {})


@router.post("/layout")
async def save_layout(layout: LayoutUpdate):
    # only the layout is replaced; aliases/egus/etc. are kept
    with edit_config() as config:
        config.setdefault("layouts", {})
        config["layouts"]["default"] = layout.model_dump()
    return {"status": "ok"}
