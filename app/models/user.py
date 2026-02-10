from sqlalchemy import Column, String, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from app.database import Base

class UserRole(str, enum.Enum):
    CUSTOMER = "customer"
    DRIVER = "driver"
    ADMIN = "admin"

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), nullable=False)
    first_name = Column(String(100))
    last_name = Column(String(100))
    profile_photo_url = Column(String)
    is_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    driver_profile = relationship("Driver", back_populates="user", uselist=False)
    tow_requests_as_customer = relationship(
        "TowRequest",
        foreign_keys="[TowRequest.customer_id]",
        back_populates="customer"
    )
    
    tow_requests_as_driver = relationship(
        "TowRequest",
        primaryjoin="User.id==TowRequest.driver_id",
        back_populates="driver",
        foreign_keys="[TowRequest.driver_id]"
    )
    notifications = relationship("Notification", back_populates="user")
    support_tickets = relationship("SupportTicket", back_populates="user")
    
    @property
    def full_name(self):
        
        return f"{self.first_name} {self.last_name}".strip()
