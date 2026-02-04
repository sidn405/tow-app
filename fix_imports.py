"""
Fix Missing __init__.py Files
Run this script from the backend directory to create all missing __init__.py files
"""
import os
from pathlib import Path

# Get the backend directory
BACKEND_DIR = Path(__file__).parent

# Define all __init__.py files and their content
init_files = {
    "app/__init__.py": '# TowTruck Platform Application\n__version__ = "1.0.0"\n',
    
    "app/api/__init__.py": "# API package\n",
    
    "app/api/v1/__init__.py": "# API v1 endpoints\n",
    
    "app/models/__init__.py": """from app.models.user import User, UserRole
from app.models.driver import Driver, ApprovalStatus, BackgroundCheckStatus
from app.models.vehicle import Vehicle
from app.models.service_type import ServiceType, CustomerVehicleType, TowReason
from app.models.tow_request import TowRequest, TowStatus, PaymentStatus
from app.models.other import (
    TowRequestOffer, OfferResponse,
    LocationHistory,
    Transaction, TransactionType, TransactionStatus,
    SupportTicket, SupportMessage, TicketStatus, TicketPriority,
    Notification, NotificationType,
    PromoCode
)

__all__ = [
    "User", "UserRole",
    "Driver", "ApprovalStatus", "BackgroundCheckStatus",
    "Vehicle",
    "ServiceType", "CustomerVehicleType", "TowReason",
    "TowRequest", "TowStatus", "PaymentStatus",
    "TowRequestOffer", "OfferResponse",
    "LocationHistory",
    "Transaction", "TransactionType", "TransactionStatus",
    "SupportTicket", "SupportMessage", "TicketStatus", "TicketPriority",
    "Notification", "NotificationType",
    "PromoCode"
]
""",
    
    "app/schemas/__init__.py": """from app.schemas.user import (
    UserBase,
    UserCreate,
    UserLogin,
    UserUpdate,
    UserResponse,
    TokenResponse,
    PasswordResetRequest,
    PasswordReset,
)
from app.schemas.driver import (
    DriverCreate,
    DriverUpdate,
    DriverResponse,
    DriverLocationUpdate,
    DriverToggleOnline,
    DriverEarnings,
    DriverApproval,
)
from app.schemas.tow_request import (
    LocationPoint,
    TowQuoteRequest,
    TowQuoteResponse,
    TowRequestCreate,
    TowRequestResponse,
    TowStatusUpdate,
    TowRating,
    TowCancellation,
    ActiveTowTracking,
)

__all__ = [
    # User schemas
    "UserBase",
    "UserCreate",
    "UserLogin",
    "UserUpdate",
    "UserResponse",
    "TokenResponse",
    "PasswordResetRequest",
    "PasswordReset",
    # Driver schemas
    "DriverCreate",
    "DriverUpdate",
    "DriverResponse",
    "DriverLocationUpdate",
    "DriverToggleOnline",
    "DriverEarnings",
    "DriverApproval",
    # Tow request schemas
    "LocationPoint",
    "TowQuoteRequest",
    "TowQuoteResponse",
    "TowRequestCreate",
    "TowRequestResponse",
    "TowStatusUpdate",
    "TowRating",
    "TowCancellation",
    "ActiveTowTracking",
]
""",
    
    "app/services/__init__.py": """from app.services.auth_service import AuthService
from app.services.pricing_service import PricingService
from app.services.matching_service import MatchingService
from app.services.payment_service import PaymentService
from app.services.notification_service import NotificationService

__all__ = [
    "AuthService",
    "PricingService",
    "MatchingService",
    "PaymentService",
    "NotificationService",
]
""",
    
    "app/utils/__init__.py": """from app.utils.geo import (
    calculate_distance,
    calculate_eta,
    format_point_for_db,
    parse_point_from_db,
    is_within_service_area,
    get_bounds,
)

__all__ = [
    "calculate_distance",
    "calculate_eta",
    "format_point_for_db",
    "parse_point_from_db",
    "is_within_service_area",
    "get_bounds",
]
""",
    
    "app/workers/__init__.py": """# Background workers for async tasks
# TODO: Implement Celery workers for:
# - Driver matching
# - Notification sending
# - Payment processing
# - Location history cleanup
""",
}

def create_init_files():
    """Create all __init__.py files"""
    created = []
    already_exists = []
    
    for filepath, content in init_files.items():
        full_path = BACKEND_DIR / filepath
        
        # Create directory if it doesn't exist
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create file if it doesn't exist
        if not full_path.exists():
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            created.append(filepath)
            print(f"✅ Created: {filepath}")
        else:
            already_exists.append(filepath)
            print(f"⏭️  Already exists: {filepath}")
    
    print(f"\n📊 Summary:")
    print(f"   Created: {len(created)} files")
    print(f"   Already existed: {len(already_exists)} files")
    print(f"\n🎉 All __init__.py files are in place!")

if __name__ == "__main__":
    print("🔧 Creating missing __init__.py files...\n")
    create_init_files()
