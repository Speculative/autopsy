"""
FastAPI WebSocket server for live mode autopsy reporting.

This module provides a WebSocket server that streams autopsy report updates
in real-time to connected clients.
"""

import asyncio
import atexit
import os
from threading import Thread
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

app = FastAPI(title="Autopsy Live Server")
connections: Set[WebSocket] = set()

# Server state
_server_thread = None
_server = None
_loop = None
_logs_transmitted = False  # Track if logs have been sent to a client at least once


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for streaming autopsy report updates."""
    global _logs_transmitted

    await websocket.accept()
    connections.add(websocket)

    try:
        # Send full snapshot on connect
        from autopsy import report
        snapshot = {
            "type": "snapshot",
            "data": report.to_json()
        }
        await websocket.send_json(snapshot)

        # Mark that logs have been transmitted to at least one client
        _logs_transmitted = True

        # Keep connection alive and listen for messages
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connections.discard(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        connections.discard(websocket)


async def broadcast_update(update: dict):
    """
    Broadcast an update to all connected clients.

    Args:
        update: Dictionary containing the update to broadcast
    """
    disconnected = set()
    for connection in connections:
        try:
            await connection.send_json(update)
        except Exception:
            disconnected.add(connection)

    # Clean up disconnected clients
    for conn in disconnected:
        connections.discard(conn)


# Serve the live mode HTML build
AUTOPSY_DIR = os.path.join(os.path.dirname(__file__))


@app.get("/")
async def serve_live_html():
    """Serve the live mode HTML interface."""
    html_path = os.path.join(AUTOPSY_DIR, "live.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    else:
        return {
            "error": "Live mode HTML not built",
            "instructions": "Run: cd autopsy_html && npm run build:live"
        }


def start_server(host: str, port: int):
    """
    Start FastAPI server in background thread.

    Args:
        host: Host to bind to
        port: Port to bind to
    """
    global _server_thread, _server, _loop

    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn not installed. Install with: uv pip install -e '.[live]'")
        return

    # Create new event loop for the server thread
    def run_server():
        global _loop
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)

        config = uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level="warning",
            loop="asyncio"
        )
        server = uvicorn.Server(config)
        _loop.run_until_complete(server.serve())

    _server_thread = Thread(target=run_server, daemon=True)
    _server_thread.start()

    # Wait a moment for server to start
    import time
    time.sleep(0.5)

    # Register shutdown
    atexit.register(shutdown_server)

    print(f"🔴 Autopsy live mode enabled")
    print(f"   WebSocket: ws://{host}:{port}/ws")
    print(f"   Web UI: http://{host}:{port}/")


def shutdown_server():
    """Stop the server gracefully."""
    global _server, _loop

    if _loop:
        try:
            # Cancel all tasks
            for task in asyncio.all_tasks(_loop):
                task.cancel()
        except Exception:
            pass


def queue_broadcast(update: dict):
    """
    Queue an update for broadcasting without blocking.

    This is called from the main thread and schedules the broadcast
    on the server's event loop.

    Args:
        update: Dictionary containing the update to broadcast
    """
    global _loop

    if _loop and _loop.is_running():
        # Schedule the coroutine on the server's event loop
        asyncio.run_coroutine_threadsafe(broadcast_update(update), _loop)


def logs_transmitted() -> bool:
    """
    Check if logs have been transmitted to at least one client.

    Returns:
        True if logs have been sent to a client, False otherwise
    """
    global _logs_transmitted
    return _logs_transmitted
