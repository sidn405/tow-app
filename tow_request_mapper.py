"""
Helper service to map frontend simple data to backend UUID system
Add this to: app/services/tow_request_helper.py
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, Dict, Any
from uuid import UUID

class TowRequestMapper:
    """Maps frontend simple data to backend UUID-based lookup tables"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def map_vehicle_type(self, vehicle_type_name: str) -> Optional[UUID]:
        """Map vehicle type string to UUID"""
        from app.models import CustomerVehicleType
        
        result = await self.db.execute(
            select(CustomerVehicleType).where(
                CustomerVehicleType.name == vehicle_type_name
            )
        )
        vehicle_type = result.scalar_one_or_none()
        
        if vehicle_type:
            return vehicle_type.id
        
        # Fallback to 'sedan' if not found
        result = await self.db.execute(
            select(CustomerVehicleType).where(
                CustomerVehicleType.name == 'sedan'
            )
        )
        fallback = result.scalar_one_or_none()
        return fallback.id if fallback else None
    
    async def map_tow_reason(self, reason_name: str) -> Optional[UUID]:
        """Map tow reason string to UUID"""
        from app.models import TowReason
        
        result = await self.db.execute(
            select(TowReason).where(
                TowReason.name == reason_name
            )
        )
        tow_reason = result.scalar_one_or_none()
        
        if tow_reason:
            return tow_reason.id
        
        # Fallback to 'other'
        result = await self.db.execute(
            select(TowReason).where(
                TowReason.name == 'other'
            )
        )
        fallback = result.scalar_one_or_none()
        return fallback.id if fallback else None
    
    async def determine_service_type(
        self, 
        vehicle_type_name: str,
        is_awd: bool = False,
        is_damaged: bool = False,
        is_lowered: bool = False
    ) -> Optional[UUID]:
        """Determine appropriate service type based on vehicle requirements"""
        from app.models import ServiceType
        
        # Logic to determine service type
        if vehicle_type_name in ['exotic', 'luxury'] or is_awd or is_lowered:
            # Requires flatbed
            service_name = 'flatbed_tow'
        elif vehicle_type_name == 'motorcycle':
            service_name = 'motorcycle_tow'
        elif vehicle_type_name in ['rv', 'large_truck'] or is_damaged:
            service_name = 'heavy_duty_tow'
        else:
            service_name = 'standard_tow'
        
        result = await self.db.execute(
            select(ServiceType).where(
                ServiceType.name == service_name
            )
        )
        service = result.scalar_one_or_none()
        
        if service:
            return service.id
        
        # Fallback to standard_tow
        result = await self.db.execute(
            select(ServiceType).where(
                ServiceType.name == 'standard_tow'
            )
        )
        fallback = result.scalar_one_or_none()
        return fallback.id if fallback else None
    
    async def map_frontend_data(self, frontend_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert frontend simple data to backend UUID-based data
        
        Frontend sends:
        {
            "vehicle_year": 2020,
            "vehicle_make": "Ferrari",
            "vehicle_model": "458",
            "vehicle_type": "exotic",
            "is_awd": false,
            "is_lowered": true,
            "is_damaged": false,
            "pickup_location": "123 Main St",
            "dropoff_location": "456 Oak Ave",
            "reason": "relocation"
        }
        
        Backend needs:
        {
            "vehicle_year": 2020,
            "vehicle_make": "Ferrari",
            "vehicle_model": "458",
            "vehicle_type_id": UUID,
            "service_type_id": UUID,
            "tow_reason_id": UUID,
            "is_awd": false,
            "is_lowered": true,
            "is_damaged": false,
            "pickup_location": {"latitude": 40.7, "longitude": -74.0},
            "dropoff_location": {"latitude": 40.8, "longitude": -74.1}
        }
        """
        
        # Map vehicle type
        vehicle_type_id = await self.map_vehicle_type(frontend_data.get('vehicle_type', 'sedan'))
        
        # Map tow reason
        tow_reason_id = await self.map_tow_reason(frontend_data.get('reason', 'other'))
        
        # Determine service type based on vehicle requirements
        service_type_id = await self.determine_service_type(
            vehicle_type_name=frontend_data.get('vehicle_type', 'sedan'),
            is_awd=frontend_data.get('is_awd', False),
            is_damaged=frontend_data.get('is_damaged', False),
            is_lowered=frontend_data.get('is_lowered', False)
        )
        
        return {
            'vehicle_year': frontend_data.get('vehicle_year'),
            'vehicle_make': frontend_data.get('vehicle_make'),
            'vehicle_model': frontend_data.get('vehicle_model'),
            'vehicle_type_id': vehicle_type_id,
            'service_type_id': service_type_id,
            'tow_reason_id': tow_reason_id,
            'is_awd': frontend_data.get('is_awd', False),
            'is_lowered': frontend_data.get('is_lowered', False),
            'is_damaged': frontend_data.get('is_damaged', False),
            # Note: You'll need to geocode these addresses to lat/long
            'pickup_address': frontend_data.get('pickup_location'),
            'dropoff_address': frontend_data.get('dropoff_location'),
        }


# Example usage in your endpoint:

"""
@router.post("/request-simple", response_model=TowRequestResponse)
async def create_tow_request_simple(
    frontend_data: dict,  # Simple frontend data
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    '''
    Simplified endpoint that accepts frontend simple data
    and converts to backend UUID system
    '''
    
    # Map frontend data to backend format
    mapper = TowRequestMapper(db)
    backend_data = await mapper.map_frontend_data(frontend_data)
    
    # TODO: Geocode addresses to lat/long
    # For now, use mock coordinates or integrate Google Maps API
    
    # Create the actual tow request using your existing logic
    # ... (rest of your create_tow_request logic)
    
    return tow_request
"""
