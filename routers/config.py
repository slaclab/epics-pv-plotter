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
import math
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
LEGACY_CONFIG_FILE = CONFIG_FILE.parent.parent / "config.json"

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


def load_config(config_file: Path | None = None) -> dict:
    config_file = config_file or CONFIG_FILE
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
    config_file = config_file or CONFIG_FILE
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
    config_file = config_file or CONFIG_FILE
    if config_file == CONFIG_FILE:
        _ensure_default_config_file()
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
    _ensure_default_config_file()
    return load_config()


_SAFE_CONFIG_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.json$")


def _ensure_default_config_file() -> None:
    """Create the default preset once, migrating the legacy root config."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with config_lock(CONFIG_FILE):
        if CONFIG_FILE.exists():
            return

        if LEGACY_CONFIG_FILE.is_file():
            try:
                with LEGACY_CONFIG_FILE.open("r", encoding="utf-8") as source:
                    config = json.load(source)
            except (json.JSONDecodeError, OSError) as error:
                log.error("Failed to migrate legacy configuration: %s", error)
                raise HTTPException(
                    status_code=500, detail="Failed to migrate legacy configuration"
                ) from error
            if not isinstance(config, dict):
                raise HTTPException(
                    status_code=500,
                    detail="Legacy configuration must contain a JSON object",
                )
            log.info("Migrating legacy config.json to configs/config.json")
        else:
            config = copy.deepcopy(DEFAULT_CONFIG)

        save_config(config, CONFIG_FILE)


def _preset_path(filename: str) -> Path:
    if not _SAFE_CONFIG_FILENAME.fullmatch(filename):
        raise HTTPException(status_code=400, detail="Invalid configuration filename")

    config_dir = CONFIG_FILE.parent.resolve()
    if filename == CONFIG_FILE.name:
        _ensure_default_config_file()

    for candidate in config_dir.glob("*.json"):
        resolved = candidate.resolve()
        if (
            candidate.name == filename
            and resolved.parent == config_dir
            and resolved.is_file()
        ):
            return resolved
    raise HTTPException(status_code=404, detail="Configuration not found")


def _read_config_file(config_file: Path) -> dict:
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
    if filename is None:
        _ensure_default_config_file()
        return CONFIG_FILE

    candidate = filename.strip()
    if not candidate:
        raise HTTPException(status_code=400, detail="Invalid configuration filename")
    if Path(candidate).name != candidate or Path(candidate).is_absolute():
        raise HTTPException(status_code=400, detail="Invalid configuration filename")

    return _preset_path(candidate)


@router.get("/config-presets")
async def list_config_presets():
    """list JSON configuration files available in the configs directory"""
    _ensure_default_config_file()
    config_dir = CONFIG_FILE.parent
    files = []
    for path in sorted(config_dir.glob("*.json")):
        if path.is_file() and path.resolve().parent == config_dir.resolve():
            files.append(path.name)
    return {"files": files}


@router.get("/config-presets/{filename}")
async def get_config_preset(filename: str):
    """read a named configuration preset without changing the active config"""
    return _read_config_file(_preset_path(filename))


@router.post("/config-presets/{filename}")
async def create_config_preset(
    filename: str,
    source: str | None = None,
    updates: Dict[str, Any] | None = None,
):
    """create a named preset, optionally copying and updating an existing preset"""
    preset_path = _preset_path_placeholder(filename)
    source_path = _preset_path(source) if source else CONFIG_FILE
    source_config = _read_config_file(source_path)
    if updates is not None:
        _merge_config_updates(source_config, updates)

    with config_lock(preset_path):
        if preset_path.exists():
            raise HTTPException(status_code=409, detail="Configuration already exists")
        save_config(copy.deepcopy(source_config), preset_path)
    return {"status": "ok", "filename": filename}


def _preset_path_placeholder(filename: str) -> Path:
    if not _SAFE_CONFIG_FILENAME.fullmatch(filename):
        raise HTTPException(status_code=400, detail="Invalid configuration filename")
    return CONFIG_FILE.parent / filename


_PRESET_UPDATE_SECTIONS = {
    "aliases",
    "egus",
    "thresholds",
    "value_formats",
    "layouts",
}


def _merge_config_updates(config: dict, updates: Dict[str, Any]) -> None:
    if not updates or updates.keys() - _PRESET_UPDATE_SECTIONS:
        raise HTTPException(status_code=422, detail="Invalid configuration sections")
    if any(not isinstance(value, dict) for value in updates.values()):
        raise HTTPException(
            status_code=422, detail="Configuration sections must be JSON objects"
        )
    _validate_preset_updates(updates)

    for section, values in updates.items():
        current = config.get(section)
        if not isinstance(current, dict):
            current = {}
            config[section] = current
        for key, value in values.items():
            if value is None:
                current.pop(key, None)
            else:
                current[key] = value


@router.patch("/config-presets/{filename}")
async def update_config_preset(filename: str, updates: Dict[str, Any]):
    """update selected configuration sections without replacing other sections"""
    preset_path = _preset_path(filename)
    with edit_config(preset_path, strict=True) as config:
        _merge_config_updates(config, updates)
    return {"status": "ok"}


def _is_finite_number(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _validate_preset_updates(updates: dict) -> None:
    for section, entries in updates.items():
        for key, value in entries.items():
            if not key:
                raise HTTPException(status_code=422, detail="PV names must not be empty")
            if value is None:
                continue
            if section in {"aliases", "egus"} and not isinstance(value, str):
                raise HTTPException(
                    status_code=422, detail=f"{section} values must be strings"
                )
            if section == "value_formats" and (
                not isinstance(value, str)
                or value not in {"regular", "exponential"}
            ):
                raise HTTPException(
                    status_code=422,
                    detail="Value formats must be 'regular' or 'exponential'",
                )
            if section == "thresholds":
                threshold = {"upper": value} if isinstance(value, (int, float)) else value
                if not isinstance(threshold, dict) or threshold.keys() - {
                    "upper",
                    "lower",
                }:
                    raise HTTPException(
                        status_code=422, detail="Invalid threshold entry"
                    )
                for bound in ("upper", "lower"):
                    number = threshold.get(bound)
                    if number is not None and not _is_finite_number(number):
                        raise HTTPException(
                            status_code=422,
                            detail="Threshold bounds must be finite numbers",
                        )
                upper = threshold.get("upper")
                lower = threshold.get("lower")
                if upper is not None and lower is not None and lower > upper:
                    raise HTTPException(
                        status_code=422,
                        detail="Lower threshold must not exceed upper threshold",
                    )
                entries[key] = threshold
            if section == "layouts":
                _validate_layout_entry(value)


def _validate_layout_entry(layout: dict) -> None:
    if not isinstance(layout, dict):
        raise HTTPException(status_code=422, detail="Layouts must be objects")
    if "plots" in layout:
        plots = layout["plots"]
        if not isinstance(plots, list):
            raise HTTPException(status_code=422, detail="Layout plots must be a list")
        for plot in plots:
            if not isinstance(plot, dict):
                raise HTTPException(status_code=422, detail="Plot entries must be objects")
            if "pvNames" in plot and (
                not isinstance(plot["pvNames"], list)
                or not all(isinstance(name, str) and name for name in plot["pvNames"])
            ):
                raise HTTPException(
                    status_code=422, detail="Plot PV names must be non-empty strings"
                )
            for field in ("id", "x", "y", "w", "h"):
                number = plot.get(field)
                if number is not None and not _is_finite_number(number):
                    raise HTTPException(status_code=422, detail=f"Invalid plot {field}")
    if "livePVNames" in layout and (
        not isinstance(layout["livePVNames"], list)
        or not all(isinstance(name, str) and name for name in layout["livePVNames"])
    ):
        raise HTTPException(
            status_code=422, detail="Live PV names must be non-empty strings"
        )
    if "globalTimeWindow" in layout and (
        not _is_finite_number(layout["globalTimeWindow"])
        or layout["globalTimeWindow"] <= 0
    ):
        raise HTTPException(status_code=422, detail="Invalid layout time window")
    if "showBeamlineStatus" in layout and not isinstance(
        layout["showBeamlineStatus"], bool
    ):
        raise HTTPException(
            status_code=422, detail="showBeamlineStatus must be a boolean"
        )


@router.post("/config")
async def update_config(config: Dict[str, Any]):
    """save the configuration"""
    _ensure_default_config_file()
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
