"""
Tow Request API routes - API ENDPOINTS ONLY, NO MODELS
Place this in: app/api/v1/tow_requests.py
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.api.v1.auth import get_current_user
from pydantic import BaseModel, Field
from typing import Optional

router = APIRouter(prefix="/api/v1/tows", tags=["tows"])


class SimpleTowRequest(BaseModel):
    """Frontend sends simple string data"""
    vehicle_year: int = Field(..., ge=1900, le=2026)
    vehicle_make: str
    vehicle_model: str
    vehicle_type: str  # sedan, luxury, exotic, etc.
    is_awd: bool = False
    is_lowered: bool = False
    is_damaged: bool = False
    pickup_location: str  # Address as string
    pickup_lat: float
    pickup_lng: float
    dropoff_location: str  # Address as string
    dropoff_lat: float
    dropoff_lng: float
    reason: str  # breakdown, accident, relocation, etc.
    vehicle_color: Optional[str] = None
    license_plate: Optional[str] = None
    pickup_notes: Optional[str] = None
    dropoff_notes: Optional[str] = None


@router.post("/request-simple")
async def create_simple_tow_request(
    request: SimpleTowRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create tow request from simple frontend format.
    
    This endpoint accepts the simple format from the frontend and converts it
    to the database format with UUIDs and proper relationships.
    """
    # Import here to avoid circular imports
    from app.services.tow_request_mapper import TowRequestMapper
    
    try:
        # Convert simple format to database UUIDs
        mapper = TowRequestMapper(db)
        mapped_data = mapper.map_request(request.dict())
        
        # TODO: Actually create the tow request in the database
        # For now, just return success with the mapped data
        
        return {
            "success": True,
            "message": "Tow request received successfully",
            "estimated_price": 125.00,  # TODO: Calculate from pricing service
            "request_id": None,  # TODO: Return actual request ID
            **mapped_data
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")


@router.get("/requests")
async def get_tow_requests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all tow requests for current user"""
    # TODO: Implement
    return {"message": "Tow requests endpoint"}


@router.get("/requests/{request_id}")
async def get_tow_request(
    request_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get specific tow request"""
    # TODO: Implement
    return {"message": f"Tow request {request_id}"}
