#!/usr/bin/env python3
import asyncio
import websockets
from urllib.parse import quote

async def test():
    pv = "BL22:SCAN:MASTER:ADC1"
    uri = f"ws://192.168.22.4:8000/ws?pv={quote(pv)}"
    print(f"Connecting to {uri}...")

    async with websockets.connect(uri) as websocket:
        print("✅ Connected!")
        while True:
            msg = await websocket.recv()
            print("Received:", msg)

asyncio.run(test())
