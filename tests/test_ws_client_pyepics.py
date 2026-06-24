#!/usr/bin/env python3
"""
WebSocket Client Test for pyepics Gateway
Corresponds to the caproto version test client
"""
import asyncio
import websockets

async def test():
    """Test WebSocket connection to pyepics gateway"""
    
    # URI configuration
    uri = "ws://192.168.22.4:8083?pv=BL22:SCAN:MASTER:ADC1"
    # Alternative PV for testing
    # uri = "ws://192.168.22.4:8082?pv=BL22:SRS570_AMP1:NAME"
    
    print(f"Connecting to {uri}...")
    print("-" * 60)
    
    try:
        # Connect with context manager (automatically closes)
        async with websockets.connect(uri) as websocket:
            print("Connected to pyepics WebSocket Gateway!")
            print("-" * 60)
            
            # Receive messages continuously
            message_count = 0
            while True:
                try:
                    message = await websocket.recv()
                    message_count += 1
                    print(f"[{message_count:4d}] Received: {message}")
                except websockets.exceptions.ConnectionClosed:
                    print("\nConnection closed by server")
                    break
                except KeyboardInterrupt:
                    print("\nInterrupted by user")
                    break
    
    except ConnectionRefusedError:
        print("Error: Connection refused")
        print("Make sure the gateway is running on port 8082")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    asyncio.run(test())
