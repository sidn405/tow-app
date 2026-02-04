from sqlalchemy import Column, String, Numeric, Integer, ForeignKey, DateTime, Text, Boolean, Enum as SQLEnum, BigInteger, ARRAY
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from geoalchemy2 import Geography
import uuid
import enum
from app.database import Base

# Tow Request Offers
class OfferResponse(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"

class TowRequestOffer(Base):
    __tablename__ = "tow_request_offers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tow_request_id = Column(UUID(as_uuid=True), ForeignKey("tow_requests.id", ondelete="CASCADE"))
    driver_id = Column(UUID(as_uuid=True), ForeignKey("drivers.id"))
    offered_at = Column(DateTime(timezone=True), server_default=func.now())
    response = Column(SQLEnum(OfferResponse), default=OfferResponse.PENDING)
    responded_at = Column(DateTime(timezone=True))
    rejection_reason = Column(Text)
    distance_from_pickup = Column(Numeric(10, 2))
    
    # Relationships
    tow_request = relationship("TowRequest", back_populates="offers")
    driver = relationship("Driver", back_populates="tow_offers")

# Location History
class LocationHistory(Base):
    __tablename__ = "location_history"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tow_request_id = Column(UUID(as_uuid=True), ForeignKey("tow_requests.id", ondelete="CASCADE"))
    driver_id = Column(UUID(as_uuid=True), ForeignKey("drivers.id"))
    location = Column(Geography(geometry_type='POINT', srid=4326), nullable=False)
    speed = Column(Numeric(5, 2))
    heading = Column(Integer)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    tow_request = relationship("TowRequest", back_populates="location_history")

# Transactions
class TransactionType(str, enum.Enum):
    CHARGE = "charge"
    REFUND = "refund"
    PAYOUT = "payout"
    PLATFORM_FEE = "platform_fee"

class TransactionStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tow_request_id = Column(UUID(as_uuid=True), ForeignKey("tow_requests.id"))
    customer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    driver_id = Column(UUID(as_uuid=True), ForeignKey("drivers.id"))
    
    amount = Column(Numeric(10, 2), nullable=False)
    transaction_type = Column(SQLEnum(TransactionType), nullable=False)
    
    stripe_charge_id = Column(String(255))
    stripe_transfer_id = Column(String(255))
    stripe_refund_id = Column(String(255))
    
    status = Column(SQLEnum(TransactionStatus), default=TransactionStatus.PENDING)
    description = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# Support Tickets
class TicketStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"

class TicketPriority(str, enum.Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    tow_request_id = Column(UUID(as_uuid=True), ForeignKey("tow_requests.id"))
    subject = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(SQLEnum(TicketStatus), default=TicketStatus.OPEN)
    priority = Column(SQLEnum(TicketPriority), default=TicketPriority.NORMAL)
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True))
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="support_tickets")
    messages = relationship("SupportMessage", back_populates="ticket")

class SupportMessage(Base):
    __tablename__ = "support_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = Column(UUID(as_uuid=True), ForeignKey("support_tickets.id", ondelete="CASCADE"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    ticket = relationship("SupportTicket", back_populates="messages")

# Notifications
class NotificationType(str, enum.Enum):
    TOW_REQUEST = "tow_request"
    TOW_UPDATE = "tow_update"
    PAYMENT = "payment"
    PROMO = "promo"
    SYSTEM = "system"

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    type = Column(SQLEnum(NotificationType))
    data = Column(JSONB)
    is_read = Column(Boolean, default=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="notifications")

# Promo Codes
class PromoCode(Base):
    __tablename__ = "promo_codes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(50), unique=True, nullable=False)
    description = Column(Text)
    discount_type = Column(String(20))  # 'percentage', 'fixed'
    discount_value = Column(Numeric(10, 2))
    max_uses = Column(Integer)
    used_count = Column(Integer, default=0)
    valid_from = Column(DateTime(timezone=True))
    valid_until = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
