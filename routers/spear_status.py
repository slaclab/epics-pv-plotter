"""Proxy SPEAR operator messages for the plotter frontend."""

import asyncio
import json
import logging
from urllib.error import URLError
from urllib.request import urlopen

from fastapi import APIRouter, HTTPException

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["spear-status"])

_SPEAR_MESSAGES_URL = "https://www-ssrl.slac.stanford.edu/spear_status/getmsgs.php"
_REQUEST_TIMEOUT_SECONDS = 5


def _fetch_spear_messages() -> dict:
    try:
        with urlopen(
            _SPEAR_MESSAGES_URL, timeout=_REQUEST_TIMEOUT_SECONDS
        ) as response:
            payload = json.load(response)
    except (URLError, OSError, json.JSONDecodeError, UnicodeDecodeError) as error:
        log.error("Failed to fetch SPEAR status messages: %s", error)
        raise HTTPException(
            status_code=502, detail="Failed to fetch SPEAR status messages"
        ) from error

    messages = payload.get("messages") if isinstance(payload, dict) else None
    if not isinstance(messages, list):
        log.error("SPEAR status endpoint returned an invalid messages list")
        raise HTTPException(
            status_code=502, detail="SPEAR status endpoint returned invalid messages"
        )
    current_time = payload.get("TIME")
    if not isinstance(current_time, str):
        log.error("SPEAR status endpoint returned an invalid TIME value")
        raise HTTPException(
            status_code=502, detail="SPEAR status endpoint returned invalid messages"
        )

    for message in messages:
        if (
            not isinstance(message, dict)
            or not isinstance(message.get("activationDate"), str)
            or not isinstance(message.get("message"), str)
        ):
            log.error("SPEAR status endpoint returned an invalid message entry")
            raise HTTPException(
                status_code=502,
                detail="SPEAR status endpoint returned invalid messages",
            )

    return {"messages": messages, "TIME": current_time}


@router.get("/spear-messages")
async def get_spear_messages():
    return await asyncio.to_thread(_fetch_spear_messages)
