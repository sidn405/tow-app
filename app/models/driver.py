from sqlalchemy import Column, String, Boolean, DateTime, Numeric, Integer, Date, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from geoalchemy2 import Geography
import uuid
import enum
from app.database import Base

class ApprovalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUSPENDED = "suspended"

class BackgroundCheckStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class Driver(Base):
    __tablename__ = "drivers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    # License information
    license_number = Column(String(100), unique=True, nullable=False)
    license_state = Column(String(2))
    license_expiry = Column(Date)
    license_photo_url = Column(String)
    
    # Insurance
    insurance_policy_number = Column(String(100))
    insurance_expiry = Column(Date)
    insurance_photo_url = Column(String)
    
    # Background check
    background_check_status = Column(SQLEnum(BackgroundCheckStatus), default=BackgroundCheckStatus.PENDING)
    background_check_date = Column(Date)
    
    # Business details
    company_name = Column(String(255))
    company_ein = Column(String(20))
    
    # Stripe Connect
    bank_account_id = Column(String(255))  # Stripe Connect account ID
    commission_rate = Column(Numeric(5, 2), default=15.00)
    
    # Performance metrics
    rating = Column(Numeric(3, 2), default=5.00)
    total_tows = Column(Integer, default=0)
    
    # Status
    is_online = Column(Boolean, default=False)
    current_location = Column(Geography(geometry_type='POINT', srid=4326))
    approval_status = Column(SQLEnum(ApprovalStatus), default=ApprovalStatus.PENDING)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="driver_profile")
    vehicles = relationship("Vehicle", back_populates="driver")
    tow_requests = relationship("TowRequest", back_populates="driver")
    tow_offers = relationship("TowRequestOffer", back_populates="driver")
