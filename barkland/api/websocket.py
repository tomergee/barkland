from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import logging

from barkland.services.simulation_manager import connected_clients, broadcast_state

logger = logging.getLogger(__name__)

router = APIRouter()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
         # Send initial state
         await broadcast_state()
         while True:
             await websocket.receive_text() # Keep connection alive
    except WebSocketDisconnect:
         if websocket in connected_clients:
             connected_clients.remove(websocket)
