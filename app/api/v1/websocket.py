from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import TowRequest, LocationHistory
from typing import Dict, List
import json
from uuid import UUID
from geoalchemy2.elements import WKTElement
from datetime import datetime

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, room_id: str):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
        self.active_connections[room_id].append(websocket)
    
    def disconnect(self, websocket: WebSocket, room_id: str):
        if room_id in self.active_connections:
            self.active_connections[room_id].remove(websocket)
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]
    
    async def broadcast_to_room(self, room_id: str, message: dict):
        if room_id in self.active_connections:
            for connection in self.active_connections[room_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    pass

manager = ConnectionManager()

@router.websocket("/ws/tracking/{tow_id}")
async def tracking_websocket(websocket: WebSocket, tow_id: str):
    """
    WebSocket endpoint for real-time location tracking
    Both customers and drivers can connect to track the tow
    """
    room_id = f"tow_{tow_id}"
    await manager.connect(websocket, room_id)
    
    try:
        while True:
            # Receive location updates from driver
            data = await websocket.receive_json()
            
            if data.get("type") == "location_update":
                # Broadcast to all connected clients
                await manager.broadcast_to_room(
                    room_id,
                    {
                        "type": "location_update",
                        "latitude": data["latitude"],
                        "longitude": data["longitude"],
                        "heading": data.get("heading"),
                        "speed": data.get("speed"),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )
            
            elif data.get("type") == "status_update":
                # Broadcast status changes
                await manager.broadcast_to_room(
                    room_id,
                    {
                        "type": "status_update",
                        "status": data["status"],
                        "message": data.get("message"),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )
            
            elif data.get("type") == "eta_update":
                # Broadcast ETA updates
                await manager.broadcast_to_room(
                    room_id,
                    {
                        "type": "eta_update",
                        "eta_minutes": data["eta_minutes"],
                        "distance_miles": data.get("distance_miles"),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)

@router.websocket("/ws/driver/{driver_id}")
async def driver_notification_websocket(websocket: WebSocket, driver_id: str):
    """
    WebSocket endpoint for driver notifications
    Receives real-time tow request notifications
    """
    room_id = f"driver_{driver_id}"
    await manager.connect(websocket, room_id)
    
    try:
        while True:
            # Keep connection alive and receive acknowledgments
            data = await websocket.receive_json()
            
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)

@router.websocket("/ws/customer/{customer_id}")
async def customer_notification_websocket(websocket: WebSocket, customer_id: str):
    """
    WebSocket endpoint for customer notifications
    Receives real-time updates about their tow request
    """
    room_id = f"customer_{customer_id}"
    await manager.connect(websocket, room_id)
    
    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_json()
            
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)

# Helper function to broadcast from other parts of the application
async def broadcast_driver_notification(driver_id: str, notification: dict):
    """Broadcast notification to specific driver"""
    await manager.broadcast_to_room(f"driver_{driver_id}", notification)

async def broadcast_customer_notification(customer_id: str, notification: dict):
    """Broadcast notification to specific customer"""
    await manager.broadcast_to_room(f"customer_{customer_id}", notification)

async def broadcast_tow_update(tow_id: str, update: dict):
    """Broadcast update to all parties tracking a tow"""
    await manager.broadcast_to_room(f"tow_{tow_id}", update)
