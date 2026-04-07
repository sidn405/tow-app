"""
Tow Request Mapper Service - ASYNC VERSION
Converts simple frontend format to database UUID format
Place this in: app/services/tow_request_mapper.py
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any
import uuid


class TowRequestMapper:
    """Maps simple frontend tow request data to database UUID format"""
    
    # Mapping of frontend string values to database lookup table values
    VEHICLE_TYPE_MAP = {
        "sedan": "sedan",
        "suv": "suv",
        "truck": "truck",
        "van": "van",
        "luxury": "luxury",
        "exotic": "exotic",
        "motorcycle": "motorcycle",
        "rv": "rv",
        "large_truck": "large_truck"
    }
    
    REASON_MAP = {
        "breakdown": "breakdown",
        "flat_tire": "flat_tire",
        "accident": "accident",
        "out_of_gas": "out_of_gas",
        "dead_battery": "dead_battery",
        "relocation": "relocation",
        "other": "other"
    }
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def map_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert simple frontend format to database format with UUIDs.
        
        Args:
            request_data: Dictionary with simple string values from frontend
            
        Returns:
            Dictionary with UUID references for database insertion
        """
        # Get vehicle type from simple string
        vehicle_type_str = request_data.get("vehicle_type", "sedan")
        vehicle_type_id = await self._get_vehicle_type_id(vehicle_type_str)
        
        # Get tow reason from simple string
        reason_str = request_data.get("reason", "other")
        tow_reason_id = await self._get_tow_reason_id(reason_str)
        
        # Determine service type based on vehicle requirements
        service_type_id = await self._determine_service_type(request_data)
        
        return {
            "vehicle_type_id": str(vehicle_type_id),
            "tow_reason_id": str(tow_reason_id),
            "service_type_id": str(service_type_id),
            "vehicle_make": request_data.get("vehicle_make"),
            "vehicle_model": request_data.get("vehicle_model"),
            "vehicle_year": request_data.get("vehicle_year"),
            "vehicle_color": request_data.get("vehicle_color"),
            "license_plate": request_data.get("license_plate"),
            "is_awd": request_data.get("is_awd", False),
            "is_lowered": request_data.get("is_lowered", False),
            "is_damaged": request_data.get("is_damaged", False),
            "pickup_address": request_data.get("pickup_location"),
            "pickup_lat": request_data.get("pickup_lat"),
            "pickup_lng": request_data.get("pickup_lng"),
            "dropoff_address": request_data.get("dropoff_location"),
            "dropoff_lat": request_data.get("dropoff_lat"),
            "dropoff_lng": request_data.get("dropoff_lng"),
            "pickup_notes": request_data.get("pickup_notes"),
            "dropoff_notes": request_data.get("dropoff_notes"),
        }
    
    async def _get_vehicle_type_id(self, vehicle_type: str) -> uuid.UUID:
        """Get vehicle type UUID from lookup table"""
        from app.models import CustomerVehicleType
        
        # Normalize the vehicle type string
        normalized = vehicle_type.lower().strip()
        db_value = self.VEHICLE_TYPE_MAP.get(normalized, "sedan")
        
        # Query the database for the UUID using async select
        result = await self.db.execute(
            select(CustomerVehicleType).filter(
                CustomerVehicleType.type_name == db_value
            )
        )
        vehicle_type_obj = result.scalars().first()
        
        if not vehicle_type_obj:
            raise ValueError(f"Vehicle type '{vehicle_type}' not found in database")
        
        return vehicle_type_obj.id
    
    async def _get_tow_reason_id(self, reason: str) -> uuid.UUID:
        """Get tow reason UUID from lookup table"""
        from app.models import TowReason
        
        # Normalize the reason string
        normalized = reason.lower().strip()
        db_value = self.REASON_MAP.get(normalized, "other")
        
        # Query the database for the UUID using async select
        result = await self.db.execute(
            select(TowReason).filter(
                TowReason.reason_name == db_value
            )
        )
        reason_obj = result.scalars().first()
        
        if not reason_obj:
            raise ValueError(f"Tow reason '{reason}' not found in database")
        
        return reason_obj.id
    
    async def _determine_service_type(self, request_data: Dict[str, Any]) -> uuid.UUID:
        """
        Determine which service type based on vehicle requirements.
        
        Rules:
        - Exotic/luxury cars → flatbed_tow
        - AWD vehicles → flatbed_tow
        - Lowered vehicles → flatbed_tow
        - Damaged vehicles → flatbed_tow
        - Motorcycles → motorcycle_tow
        - Heavy trucks → heavy_duty_tow
        - Everything else → standard_tow
        """
        from app.models import ServiceType
        
        vehicle_type = request_data.get("vehicle_type", "").lower()
        is_awd = request_data.get("is_awd", False)
        is_lowered = request_data.get("is_lowered", False)
        is_damaged = request_data.get("is_damaged", False)
        
        # Determine service type based on requirements
        if vehicle_type == "motorcycle":
            service_name = "motorcycle_tow"
        elif vehicle_type in ["large_truck", "rv"]:
            service_name = "heavy_duty_tow"
        elif vehicle_type in ["exotic", "luxury"] or is_awd or is_lowered or is_damaged:
            service_name = "flatbed_tow"
        else:
            service_name = "standard_tow"
        
        # Query the database for the UUID using async select
        result = await self.db.execute(
            select(ServiceType).filter(
                ServiceType.service_name == service_name
            )
        )
        service_obj = result.scalars().first()
        
        if not service_obj:
            raise ValueError(f"Service type '{service_name}' not found in database")
        
        return service_obj.id