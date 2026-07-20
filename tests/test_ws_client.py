#!/usr/bin/env python3
import asyncio
import websockets
from urllib.parse import quote
async def test():

    # get Uniform Resource Identifier (URI)
    # A string that uniquely identifies a resource on the internet
    '''
    URI Structure Explanation (RFC 3986):
    
    ws://localhost:8082/api/data?pv=BL22:SCAN:MASTER:ADC1&format=json#section1
    │  │   │        │   │                                                 │
    │  │   │        │   └─────────────────────────────────────────────────┴─ hier-part + query + fragment
    │  │   │        │   
    │  │   │        │   Detailed breakdown:
    │  │   │        │   ├─ Path: /api/data
    │  │   │        │   ├─ Params: between path and query (path;params?query)              
    │  │   │        │   ├─ Query: pv=BL22:SCAN:MASTER:ADC1&format=json (return json format data)
    │  │   │        │   └─ Fragment: section1
    │  │   │        │
    │  │   │        └─────── Port: 8082
    │  │   └──────────────── Host: localhost (part of authority)
    │  └──────────────────── Scheme: ws
    └─────────────────────── Full URI
    
    In WebSocket requests:
    - Full Path (websocket.request.path) = /api/data?pv=BL22:SCAN:MASTER:ADC1&format=json
      ├─ path component: /api/data
      └─ query component: pv=BL22:SCAN:MASTER:ADC1&format=json
    
    - Fragment (#section1) is NOT sent to server (browser-only)
    '''
    pv = "BL22:SCAN:MASTER:ADC1"
    uri = f"ws://192.168.22.4:8000/ws?pv={quote(pv)}"



    #uri = "ws://192.168.22.4:8082?pv=BL22:SRS570_AMP1:NAME"
    print(f"Connecting to {uri}...")
    
    try:
        # with context manager, automatically calls websocket.close()
        async with websockets.connect(uri) as websocket:
            print("✅ Connected!")
            
            # Receive messages
            #async for message in websocket:
            #    print(f"Received: {message}")
            while True:
                try:
                    message = await websocket.recv()  # wait to receive a message
                    print(f"Received: {message}")
                except websockets.exceptions.ConnectionClosed:
                    break
    except Exception as e:
        print(f"❌ Error: {e}")

asyncio.run(test())
