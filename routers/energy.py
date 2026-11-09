# routers/energy.py
"""
Energy router - monochromator energy calculated from a user-chosen encoder.

The frontend's "Add Energy" button adds a Live PV named
"<beamline>:MONO_CALC.ENERGY" (e.g. "BL22:MONO_CALC.ENERGY"). That is not a
real EPICS PV (MONO_CALC marks it as calculated): the frontend connects to
/ws/energy and this router monitors

    encoder_pv                raw encoder counts (.REP is added if no field given)
    <encoder record>.UREV     user units (deg) per revolution
    <encoder record>.EREV     encoder counts per revolution
    d_spacing_pv              crystal d-spacing, Angstrom (store IOC)
    offset_pv                 encoder offset in degrees (store IOC)

and streams the energy back in the same JSON format as a normal PV on /ws.
The math itself lives in calc/energy.py.

The encoder PV and store PV names are shared settings, kept in config.json
under "energy" next to aliases/EGUs, and edited via /api/energy-config.
"""

import asyncio
import logging
import os

import numpy as np
from fastapi import APIRouter, HTTPException, Query, Request, WebSocket
from pydantic import BaseModel, field_validator

from calc.energy import EnergyCalcError, encoder_angle_deg, bragg_energy_ev
from routers.config import load_config, save_config

log = logging.getLogger(__name__)

router = APIRouter(tags=["energy"])

# Live PV names ending with this are energy streams (must match ENERGY_SUFFIX
# in src/utils/energy.js), e.g. "BL22:MONO_CALC.ENERGY"
ENERGY_SUFFIX = ".ENERGY"
# Record part of the energy name, so it can't be mistaken for a real PV
# (must match CALC_RECORD in src/utils/energy.js)
CALC_RECORD = "MONO_CALC"

DEFAULT_ENERGY_CONFIG = {
    "encoder_pv": "BL22:SCAN:MASTER:MOTOR1.REP",
    "d_spacing_pv": "BL22:STORE:CRYSTAL_D",
    "offset_pv": "BL22:STORE:CRYSTAL_ENCODER_OFFSET",
}

# Same default as the /ws endpoint: remote CA gateways can be slow to connect
PV_CONNECT_TIMEOUT = float(os.environ.get("PV_CONNECT_TIMEOUT", "10"))

# Number of open energy WebSocket streams (for debugging / health)
active_energy_streams = 0


# ---------- settings (stored in config.json like aliases) ----------

def get_energy_config() -> dict:
    stored = load_config().get("energy", {})
    if not isinstance(stored, dict):
        stored = {}
    # Only known keys, so settings removed from the app (the old
    # "offset_units" / "resolution_field") are ignored in an older config.json.
    return {key: stored.get(key, default) for key, default in DEFAULT_ENERGY_CONFIG.items()}


class EnergyConfigUpdate(BaseModel):
    encoder_pv: str = DEFAULT_ENERGY_CONFIG["encoder_pv"]
    d_spacing_pv: str
    offset_pv: str

    #no blank value check, registered by field_validator
    @field_validator("encoder_pv", "d_spacing_pv", "offset_pv")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be empty")
        return value

    @field_validator("encoder_pv")
    @classmethod
    def add_rep_field(cls, value: str) -> str:
        return normalize_encoder_pv(value)


@router.get("/api/energy-config")
async def read_energy_config():
    """get the energy calculation settings (encoder and store PV names)"""
    return get_energy_config()


@router.post("/api/energy-config")
async def update_energy_config(update: EnergyConfigUpdate):
    """save the energy calculation settings"""
    config = load_config()
    config["energy"] = update.model_dump()
    save_config(config)
    return {"status": "ok", "energy": config["energy"]}


# ---------- helpers ----------

def normalize_encoder_pv(name: str) -> str:
    """Add .REP when the user gave a record name without a field
    (or gave an old-style energy name "<record>.ENERGY")."""
    name = name.strip()
    if name.endswith(ENERGY_SUFFIX):
        name = name[: -len(ENERGY_SUFFIX)]
    last_part = name.rsplit(":", 1)[-1]
    return name if "." in last_part else f"{name}.REP"


def energy_pv_name(encoder: str) -> str:
    """BL22:SCAN:MASTER:MOTOR1.REP -> BL22:MONO_CALC.ENERGY"""
    beamline = normalize_encoder_pv(encoder).split(":", 1)[0]
    return f"{beamline}:{CALC_RECORD}{ENERGY_SUFFIX}"


def record_field_pv(encoder_pv: str, field: str) -> str:
    """<record>.<field> for the record the encoder PV belongs to."""
    return f"{encoder_pv.rsplit('.', 1)[0]}.{field}"


def to_scalar(data):
    """First element of a caproto reading as a float, or None."""
    try:
        flat = np.asarray(data).ravel()
        value = float(flat[0]) if flat.size else None
        return value if value is not None and np.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def build_message(stream_name, input_names, latest):
    """Energy message in the /ws format, plus theta and the raw inputs."""
    values = {key: to_scalar(event.data) for key, event in latest.items()}
    worst = max(latest.values(), key=lambda event: event.metadata.severity)

    message = {
        "value": None,
        "theta": None,
        "timestamp": max(event.metadata.timestamp for event in latest.values()),
        "status": int(worst.metadata.status),
        "severity": int(worst.metadata.severity),
        "pv": stream_name,
        "inputs": {input_names[key]: values[key] for key in input_names},
    }
    try:
        theta = encoder_angle_deg(
            values["rep"], values["urev"], values["erev"], values["offset"]
        )
        message["theta"] = theta
        message["value"] = bragg_energy_ev(theta, values["d_spacing"])
    except EnergyCalcError as e:
        # value stays None: the frontend shows "---" instead of a wrong number.
        # Keep detailed error information in server logs only.
        log.warning("Energy calculation failed for %s: %s", stream_name, e)
        message["detail"] = "Energy calculation failed"
    return message


# ---------- one-shot read (easy to try from /docs) ----------

def input_pv_names(encoder: str, config: dict) -> dict:
    """The PVs the energy is calculated from, keyed by role."""
    encoder_pv = normalize_encoder_pv(encoder)
    return {
        "rep": encoder_pv,
        "urev": record_field_pv(encoder_pv, "UREV"),
        "erev": record_field_pv(encoder_pv, "EREV"),
        "d_spacing": config["d_spacing_pv"],
        "offset": config["offset_pv"],
    }


@router.get("/api/energy")
async def read_energy(
    request: Request,
    encoder: str | None = Query(
        None,
        description="Encoder PV (.REP is added if no field is given); "
                    "default: encoder_pv from /api/energy-config",
    ),
):
    """read the input PVs once and return the calculated energy (eV)"""
    config = get_energy_config()
    encoder = encoder or config["encoder_pv"]
    input_names = input_pv_names(encoder, config)
    names = list(input_names.values())
    ca_context = request.app.state.ca_context
    pvs = await ca_context.get_pvs(*names)
    results = await asyncio.gather(
        *(pv.read(data_type="time", timeout=PV_CONNECT_TIMEOUT) for pv in pvs),
        return_exceptions=True,
    )
    missing = [name for name, result in zip(names, results)
               if isinstance(result, Exception)]
    if missing:
        raise HTTPException(
            status_code=504, detail=f"Could not read: {', '.join(missing)}"
        )
    latest = dict(zip(input_names, results))
    message = build_message(energy_pv_name(encoder), input_names, latest)
    return message


# ---------- WebSocket stream ----------

@router.websocket("/ws/energy")
async def energy_websocket(
    websocket: WebSocket,
    encoder: str | None = Query(
        None,
        description="Encoder PV, e.g. BL22:SCAN:MASTER:MOTOR1.REP; "
                    "default: encoder_pv from /api/energy-config",
    ),
):
    global active_energy_streams

    await websocket.accept()

    config = get_energy_config()
    encoder = encoder or config["encoder_pv"]
    stream_name = energy_pv_name(encoder)
    input_names = input_pv_names(encoder, config)
    client_id = f"{websocket.client.host}:{websocket.client.port}:{stream_name}"
    log.info(f"⚡ Energy stream requested: {client_id} inputs={input_names}")

    # Every input update, a client disconnect and any input error all go
    # through this one queue, so the main loop handles them in order.
    queue: asyncio.Queue = asyncio.Queue()
    tasks = []
    active_energy_streams += 1

    async def pump(key, pv):
        try:
            async for event in pv.subscribe(data_type="time"):
                queue.put_nowait((key, event))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            queue.put_nowait(("__error__", f"{input_names[key]}: {e}"))

    async def watch_client():
        # Detects a closed browser even when no PV is updating
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                queue.put_nowait(("__disconnect__", None))
                return

    try:
        ca_context = websocket.app.state.ca_context
        names = list(input_names.values())
        pvs = await ca_context.get_pvs(*names)
        results = await asyncio.gather(
            *(pv.wait_for_connection(timeout=PV_CONNECT_TIMEOUT) for pv in pvs),
            return_exceptions=True,
        )
        missing = [name for name, result in zip(names, results)
                   if isinstance(result, Exception)]
        if missing:
            raise RuntimeError(f"Could not connect to: {', '.join(missing)}")

        tasks.append(asyncio.create_task(watch_client()))
        for key, pv in zip(input_names, pvs):
            tasks.append(asyncio.create_task(pump(key, pv)))

        latest = {}
        while True:
            # Take everything already queued, so a burst of fast encoder
            # updates is sent as one up-to-date value instead of a backlog.
            batch = [await queue.get()]
            while not queue.empty():
                batch.append(queue.get_nowait())

            for key, payload in batch:
                if key == "__disconnect__":
                    log.info(f"🔌 Energy client disconnected: {client_id}")
                    return
                if key == "__error__":
                    raise RuntimeError(payload)
                latest[key] = payload

            # Wait until every input has reported at least once
            if len(latest) < len(input_names):
                continue

            await websocket.send_json(
                build_message(stream_name, input_names, latest)
            )

    except Exception as e:
        log.error(f"❌ Energy error for {client_id}: {e}")
        try:
            await websocket.send_json({"error": str(e), "pv": stream_name})
            await websocket.close(code=1011)
        except Exception:
            pass  # client already gone

    finally:
        # Cancelling the pump tasks closes their subscriptions
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        active_energy_streams -= 1
        log.info(f"🧹 Cleaned up energy stream {client_id}")
