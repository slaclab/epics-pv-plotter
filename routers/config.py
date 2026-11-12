# routers/config.py
"""
Configuration API router - handles shared aliases and layouts.
Stored in config.json so all browsers share the same settings.
"""

import copy
import errno
import fcntl
import json
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Any, Iterator, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

log = logging.getLogger(__name__)

# create router, setup prefix and tags
router = APIRouter(prefix="/api", tags=["config"])

# set up the files's path and file name
CONFIG_FILE = Path(__file__).parent.parent / "config.json"

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


def load_config() -> dict:
    # deepcopy: callers mutate the result, which must not change the defaults
    if not CONFIG_FILE.exists():
        return copy.deepcopy(DEFAULT_CONFIG)
    try:
        # open config file and load the json data
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        log.warning(f"Failed to read config, using default: {e}")
        return copy.deepcopy(DEFAULT_CONFIG)


def save_config(config: dict) -> None:
    tmp = CONFIG_FILE.with_suffix(".json.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        try:
            tmp.replace(CONFIG_FILE)   # replace the old configuration file
        except OSError as e:
            if e.errno != errno.EBUSY:
                raise
            # CONFIG_FILE is a bind-mounted single file (e.g. Docker's
            # `volumes: - ./config.json:/app/config.json`), which can't be
            # atomically replaced via rename - write in place instead.
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            tmp.unlink(missing_ok=True)
    except IOError as e:
        log.error(f"Failed to save config: {e}")
        raise HTTPException(status_code=500, detail="Failed to save config")


@contextmanager
def config_lock() -> Iterator[None]:
    """
    Exclusive lock on config.json across processes (e.g. several uvicorn
    workers). Every writer must hold it for its whole read-modify-write so
    one request can't save a stale copy over another's change.

    Never `await` while holding it: the flock call blocks, and a second
    coroutine in the same process waiting on it would stall the event loop.
    """
    lock_path = CONFIG_FILE.with_suffix(".json.lock")
    with open(lock_path, "w", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


@contextmanager
def edit_config() -> Iterator[dict]:
    """
    Locked read-modify-write of config.json:

        with edit_config() as config:
            config["aliases"][pv] = alias

    The config is saved when the block ends normally; if the block raises
    (e.g. HTTPException), nothing is written.
    """
    with config_lock():
        config = load_config()
        yield config
        save_config(config)


# ---------- complete setup of the router ----------

@router.get("/config")
async def get_config():
    """get the complete configuration"""
    return load_config()


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
