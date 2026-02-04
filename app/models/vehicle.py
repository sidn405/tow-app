from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy import DateTime
import uuid
from app.database import Base

class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    driver_id = Column(UUID(as_uuid=True), ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False)
    
    vehicle_type = Column(String(50), nullable=False)  # 'flatbed', 'wheel_lift', 'integrated', 'hook_chain'
    make = Column(String(100))
    model = Column(String(100))
    year = Column(Integer)
    license_plate = Column(String(20))
    vin = Column(String(50))
    insurance_policy = Column(String(100))
    capacity_weight = Column(Integer)  # in pounds
    can_tow_types = Column(ARRAY(String))  # ['sedan', 'suv', 'truck', 'motorcycle', 'van']
    photos = Column(ARRAY(String))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    driver = relationship("Driver", back_populates="vehicles")
