from pydantic import BaseModel, Field
from typing import Optional, Tuple
from datetime import datetime, date
from uuid import UUID
from decimal import Decimal
from app.models.driver import ApprovalStatus, BackgroundCheckStatus

class DriverCreate(BaseModel):
    license_number: str
    license_state: str
    license_expiry: date
    company_name: Optional[str] = None
    company_ein: Optional[str] = None

class DriverUpdate(BaseModel):
    license_number: Optional[str] = None
    license_state: Optional[str] = None
    license_expiry: Optional[date] = None
    insurance_policy_number: Optional[str] = None
    insurance_expiry: Optional[date] = None
    company_name: Optional[str] = None
    company_ein: Optional[str] = None

class DriverResponse(BaseModel):
    id: UUID
    user_id: UUID
    license_number: str
    license_state: Optional[str]
    rating: Decimal
    total_tows: int
    is_online: bool
    approval_status: ApprovalStatus
    background_check_status: BackgroundCheckStatus
    bank_account_id: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

class DriverLocationUpdate(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    speed: Optional[float] = None
    heading: Optional[int] = Field(None, ge=0, le=359)

class DriverToggleOnline(BaseModel):
    is_online: bool
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)

class DriverEarnings(BaseModel):
    total_earnings: Decimal
    completed_tows: int
    average_rating: Decimal
    total_distance: Decimal
    earnings_this_week: Decimal
    earnings_this_month: Decimal

class DriverApproval(BaseModel):
    approval_status: ApprovalStatus
    rejection_reason: Optional[str] = None
