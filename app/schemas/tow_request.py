from pydantic import BaseModel, Field
from typing import Optional, Tuple
from datetime import datetime
from uuid import UUID
from decimal import Decimal
from app.models.tow_request import TowStatus, PaymentStatus

class LocationPoint(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)

class TowQuoteRequest(BaseModel):
    pickup_location: LocationPoint
    dropoff_location: LocationPoint
    service_type_id: UUID
    vehicle_type_id: UUID
    tow_reason_id: UUID

class TowQuoteResponse(BaseModel):
    customer_price: Decimal
    driver_payout: Decimal
    platform_fee: Decimal
    stripe_fee: Decimal
    distance_miles: Decimal
    estimated_duration_minutes: int
    breakdown: dict

class TowRequestCreate(BaseModel):
    
    vehicle_year: int = Field(..., ge=1900, le=2026)
    vehicle_make: str = Field(..., min_length=1, max_length=100)
    vehicle_model: str = Field(..., min_length=1, max_length=100)
    vehicle_type: str  # sedan, suv, luxury, exotic, motorcycle, rv, large_truck
    vehicle_color: Optional[str] = None
    license_plate: Optional[str] = None
    is_awd: bool = False
    is_lowered: bool = False
    is_damaged: bool = False
    pickup_location: str
    dropoff_location: str
    reason: str   
    dropoff_notes: Optional[str] = None
    service_type_id: UUID
    vehicle_type_id: UUID    
    pickup_notes: Optional[str] = None

class TowRequestResponse(BaseModel):
    id: UUID
    customer_id: UUID
    driver_id: Optional[UUID]
    service_type_id: UUID
    vehicle_type_id: UUID
    tow_reason_id: UUID
    vehicle_year: int
    vehicle_make: str
    vehicle_model: str
    vehicle_type: str
    is_awd: bool
    is_lowered: bool
    is_damaged: bool
    pickup_address: str
    dropoff_address: str
    distance_miles: Optional[Decimal]
    quoted_price: Optional[Decimal]
    driver_payout: Optional[Decimal]
    platform_fee: Optional[Decimal]
    status: TowStatus
    payment_status: PaymentStatus
    requested_at: datetime
    accepted_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True

class TowStatusUpdate(BaseModel):
    status: TowStatus
    notes: Optional[str] = None

class TowRating(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    review: Optional[str] = None

class TowCancellation(BaseModel):
    reason: str

class ActiveTowTracking(BaseModel):
    tow_id: UUID
    driver_name: str
    driver_phone: str
    driver_rating: Decimal
    vehicle_info: str
    current_location: Optional[LocationPoint]
    status: TowStatus
    eta_minutes: Optional[int]
    distance_to_destination: Optional[Decimal]
