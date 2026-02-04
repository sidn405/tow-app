from sqlalchemy import Column, String, Boolean, Numeric, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy import DateTime, Text
import uuid
from app.database import Base

class ServiceType(Base):
    __tablename__ = "service_types"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    base_price = Column(Numeric(10, 2))
    per_mile_rate = Column(Numeric(10, 2))
    included_miles = Column(Integer, default=5)
    is_active = Column(Boolean, default=True)

class CustomerVehicleType(Base):
    __tablename__ = "customer_vehicle_types"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(50), nullable=False)
    price_multiplier = Column(Numeric(3, 2), default=1.00)
    description = Column(Text)

class TowReason(Base):
    __tablename__ = "tow_reasons"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    requires_flatbed = Column(Boolean, default=False)
    price_adjustment = Column(Numeric(10, 2), default=0.00)
    description = Column(Text)
