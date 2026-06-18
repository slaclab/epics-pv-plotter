#!/usr/bin/env python3
"""
EPICS PVAccess WebSocket Gateway
Bridges EPICS PVs to WebSocket clients using p4p
"""

import asyncio
import websockets
import json
import logging
from p4p.client.thread import Context
from urllib.parse import urlparse, parse_qs
import signal
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)

logger = logging.getLogger(__name__)

class EPICSWebSocketGateway:
    def __init__(self, host='0.0.0.0', port=8080):
        self.host = host
        self.port = port
        self.ctx = Context('pva')  # PVAccess context
        self.active_connections = {}
        
    async def handle_client(self, websocket, path):
        """Handle WebSocket connection for a single PV"""
        # Extract PV name from URL
        parsed = urlparse(path)
        query_params = parse_qs(parsed.query)
        pv_name = query_params.get('pv', [None])[0]
        
        if not pv_name:
            # Try to get from path
            pv_name = parsed.path.strip('/')
        
        if not pv_name:
            logger.warning("Connection without PV name")
            await websocket.close(1002, "No PV name specified")
            return
        
        client_id = f"{websocket.remote_address}:{pv_name}"
        logger.info(f"✓ CONNECTED: {pv_name} from {websocket.remote_address}")
        
        try:
            # Callback for PV updates
            async def on_update(value):
                try:
                    # Handle different value types
                    if hasattr(value, 'raw'):
                        val = float(value.raw.value)
                    elif hasattr(value, 'value'):
                        val = float(value.value)
                    else:
                        val = float(value)
                    
                    message = {
                        'type': 'update',
                        'pv': pv_name,
                        'value': val,
                        'timestamp': value.timestamp.tolist() if hasattr(value, 'timestamp') else None
                    }
                    
                    if websocket.open:
                        await websocket.send(json.dumps(message))
                        
                except Exception as e:
                    logger.error(f"Error processing value for {pv_name}: {e}")
            
            # Subscribe to PV using p4p monitor
            def sync_callback(value):
                """Synchronous callback that schedules async update"""
                asyncio.create_task(on_update(value))
            
            # Start monitoring
            subscription = self.ctx.monitor(pv_name, sync_callback)
            self.active_connections[client_id] = subscription
            
            # Keep connection alive
            await websocket.wait_closed()
            
        except Exception as e:
            logger.error(f"Error with {pv_name}: {e}")
            
        finally:
            # Cleanup
            if client_id in self.active_connections:
                self.active_connections[client_id].close()
                del self.active_connections[client_id]
            logger.info(f"✗ DISCONNECTED: {pv_name}")
    
    async def start(self):
        """Start the WebSocket server"""
        logger.info("╔════════════════════════════════════════════════════════╗")
        logger.info("║   EPICS PVAccess WebSocket Gateway                     ║")
        logger.info(f"║   Running on ws://{self.host}:{self.port}                       ║")
        logger.info("╚════════════════════════════════════════════════════════╝")
        logger.info("")
        logger.info("Usage: ws://localhost:8080?pv=YOUR:PV:NAME")
        logger.info("")
        
        async with websockets.serve(self.handle_client, self.host, self.port):
            await asyncio.Future()  # Run forever
    
    def shutdown(self):
        """Cleanup on shutdown"""
        logger.info("\n🛑 Shutting down...")
        for conn_id, subscription in self.active_connections.items():
            subscription.close()
        self.ctx.close()

def main():
    gateway = EPICSWebSocketGateway(host='0.0.0.0', port=8080)
    
    # Handle shutdown gracefully
    def signal_handler(sig, frame):
        gateway.shutdown()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        asyncio.run(gateway.start())
    except KeyboardInterrupt:
        gateway.shutdown()

if __name__ == '__main__':
    main()
