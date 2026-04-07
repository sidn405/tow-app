from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Column, String, Numeric, Integer, ForeignKey, DateTime, Text, Enum as SQLEnum, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from geoalchemy2 import Geography
import uuid
import enum
from app.database import Base
from sqlalchemy.orm import Session
from app.database import get_db

from app.models import User
from app.api.v1.auth import get_current_user
from pydantic import BaseModel
from pydantic import BaseModel, Field
from typing import Optional

router = APIRouter(prefix="/api/v1/tows", tags=["tows"])

# Add this schema
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
    dropoff_location: str  # Address as string
    reason: str  # breakdown, accident, relocation, etc.
    vehicle_color: Optional[str] = None
    license_plate: Optional[str] = None
    pickup_notes: Optional[str] = None
    dropoff_notes: Optional[str] = None


class TowStatus(str, enum.Enum):
    PENDING = "pending"
    SEARCHING = "searching"
    ACCEPTED = "accepted"
    EN_ROUTE_PICKUP = "en_route_pickup"
    ARRIVED_PICKUP = "arrived_pickup"
    VEHICLE_LOADED = "vehicle_loaded"
    EN_ROUTE_DROPOFF = "en_route_dropoff"
    ARRIVED_DROPOFF = "arrived_dropoff"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    REFUNDED = "refunded"
    FAILED = "failed"

class TowRequest(Base):
    __tablename__ = "tow_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    driver_id = Column(UUID(as_uuid=True), ForeignKey("drivers.id"))
    service_type_id = Column(UUID(as_uuid=True), ForeignKey("service_types.id"))
    vehicle_type_id = Column(UUID(as_uuid=True), ForeignKey("customer_vehicle_types.id"))
    tow_reason_id = Column(UUID(as_uuid=True), ForeignKey("tow_reasons.id"))
    # Add these new fields:
    vehicle_year = Column(Integer)
    vehicle_make = Column(String(100))
    vehicle_model = Column(String(100))
    vehicle_type = Column(String(50))  # sedan, suv, luxury, exotic, etc.
    is_awd = Column(Boolean, default=False)
    is_lowered = Column(Boolean, default=False)
    is_damaged = Column(Boolean, default=False)
    
    # Location details
    pickup_location = Column(Geography(geometry_type='POINT', srid=4326), nullable=False)
    pickup_address = Column(Text, nullable=False)
    pickup_notes = Column(Text)
    dropoff_location = Column(Geography(geometry_type='POINT', srid=4326), nullable=False)
    dropoff_address = Column(Text, nullable=False)
    dropoff_notes = Column(Text)
    distance_miles = Column(Numeric(10, 2))
    
    # Vehicle details
    vehicle_make = Column(String(100))
    vehicle_model = Column(String(100))
    vehicle_year = Column(Integer)
    vehicle_color = Column(String(50))
    license_plate = Column(String(20))
    
    # Pricing
    quoted_price = Column(Numeric(10, 2))
    driver_payout = Column(Numeric(10, 2))
    platform_fee = Column(Numeric(10, 2))
    stripe_fee = Column(Numeric(10, 2))
    
    # Status tracking
    status = Column(SQLEnum(TowStatus), nullable=False, default=TowStatus.PENDING)
    requested_at = Column(DateTime(timezone=True), server_default=func.now())
    accepted_at = Column(DateTime(timezone=True))
    arrived_pickup_at = Column(DateTime(timezone=True))
    loaded_at = Column(DateTime(timezone=True))
    arrived_dropoff_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    cancelled_at = Column(DateTime(timezone=True))
    cancellation_reason = Column(Text)
    
    # Payment
    payment_intent_id = Column(String(255))
    payment_status = Column(SQLEnum(PaymentStatus), default=PaymentStatus.PENDING)
    
    # Rating
    customer_rating = Column(Integer)
    customer_review = Column(Text)
    driver_rating = Column(Integer)
    driver_review = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    customer = relationship("User", foreign_keys=[customer_id], back_populates="tow_requests_as_customer")
    driver = relationship("Driver", foreign_keys=[driver_id], back_populates="tow_requests")
    service_type = relationship("ServiceType")
    vehicle_type = relationship("CustomerVehicleType")
    tow_reason = relationship("TowReason")
    offers = relationship("TowRequestOffer", back_populates="tow_request")
    location_history = relationship("LocationHistory", back_populates="tow_request")

@router.post("/request-simple")
async def create_simple_tow_request(
    request: SimpleTowRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create tow request from simple frontend format"""
    from app.services.tow_request_mapper import TowRequestMapper
    
    # Convert simple format to database UUIDs
    mapper = TowRequestMapper(db)
    mapped_data = mapper.map_request(request.dict())
    
    # TODO: Create tow request in database using mapped_data
    # For now, just return success
    
    return {
        "message": "Tow request received",
        "estimated_price": 125.00,  # Placeholder
        **mapped_data
    }