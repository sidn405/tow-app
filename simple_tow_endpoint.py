"""
Add this to app/api/v1/tow_requests.py

This is a simplified wrapper endpoint that accepts frontend simple data
and converts it to your existing UUID-based system
"""

from pydantic import BaseModel, Field
from typing import Optional

# Add this schema
class SimpleTowRequest(BaseModel):
    """Frontend sends simple string data"""
    vehicle_year: int = Field(..., ge=1900, le=2026)
    vehicle_make: str
    vehicle_model: str
    vehicle_type: str  # sedan, luxury, exotic, etc.
    is_awd: bool = False
    is_lowered: bool = False
    is_damaged: bool = False
    pickup_location: str  # Address as string
    dropoff_location: str  # Address as string
    reason: str  # breakdown, accident, relocation, etc.
    vehicle_color: Optional[str] = None
    license_plate: Optional[str] = None
    pickup_notes: Optional[str] = None
    dropoff_notes: Optional[str] = None


# Add this new endpoint alongside your existing one
@router.post("/request-simple", response_model=TowRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_tow_request_simple(
    request: SimpleTowRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Simplified endpoint for frontend
    Accepts simple string data and converts to UUID-based system
    Then calls your existing sophisticated pricing/matching logic
    """
    
    from app.services.tow_request_mapper import TowRequestMapper
    from app.models import LocationInput
    
    # Map frontend simple data to backend UUIDs
    mapper = TowRequestMapper(db)
    
    # Get UUIDs for lookup tables
    vehicle_type_id = await mapper.map_vehicle_type(request.vehicle_type)
    tow_reason_id = await mapper.map_tow_reason(request.reason)
    service_type_id = await mapper.determine_service_type(
        vehicle_type_name=request.vehicle_type,
        is_awd=request.is_awd,
        is_damaged=request.is_damaged,
        is_lowered=request.is_lowered
    )
    
    if not vehicle_type_id or not tow_reason_id or not service_type_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid vehicle type, reason, or service type"
        )
    
    # TODO: Geocode addresses to lat/long
    # For now, using NYC coordinates as placeholder
    # Install: pip install googlemaps
    # Then use Google Maps API to geocode
    
    # Placeholder coordinates (replace with real geocoding)
    pickup_lat, pickup_lng = 40.7128, -74.0060
    dropoff_lat, dropoff_lng = 40.7589, -73.9851
    
    # Create LocationInput objects for your existing endpoint
    pickup_location = LocationInput(
        latitude=pickup_lat,
        longitude=pickup_lng
    )
    
    dropoff_location = LocationInput(
        latitude=dropoff_lat,
        longitude=dropoff_lng
    )
    
    # Create TowRequestCreate object for your existing logic
    tow_data = TowRequestCreate(
        service_type_id=service_type_id,
        vehicle_type_id=vehicle_type_id,
        tow_reason_id=tow_reason_id,
        pickup_location=pickup_location,
        pickup_address=request.pickup_location,  # Store original address
        pickup_notes=request.pickup_notes,
        dropoff_location=dropoff_location,
        dropoff_address=request.dropoff_location,
        dropoff_notes=request.dropoff_notes,
        vehicle_make=request.vehicle_make,
        vehicle_model=request.vehicle_model,
        vehicle_year=request.vehicle_year,
        vehicle_color=request.vehicle_color,
        license_plate=request.license_plate
    )
    
    # Calculate distance
    distance = calculate_distance(
        (pickup_lat, pickup_lng),
        (dropoff_lat, dropoff_lng)
    )
    
    # Get pricing using YOUR existing sophisticated pricing service
    pricing_service = PricingService(db)
    pricing = await pricing_service.calculate_tow_price(
        distance_miles=distance,
        service_type_id=str(service_type_id),
        vehicle_type_id=str(vehicle_type_id),
        tow_reason_id=str(tow_reason_id)
    )
    
    # Create payment intent
    payment_service = PaymentService(db)
    payment_intent = await payment_service.create_payment_intent(
        tow_request_id=None,
        customer_id=current_user.id,
        amount=pricing["customer_price"]
    )
    
    # Create tow request with ALL the fields
    from geoalchemy2.elements import WKTElement
    tow_request = TowRequest(
        customer_id=current_user.id,
        service_type_id=service_type_id,
        vehicle_type_id=vehicle_type_id,
        tow_reason_id=tow_reason_id,
        pickup_location=WKTElement(f"POINT({pickup_lng} {pickup_lat})", srid=4326),
        pickup_address=request.pickup_location,
        pickup_notes=request.pickup_notes,
        dropoff_location=WKTElement(f"POINT({dropoff_lng} {dropoff_lat})", srid=4326),
        dropoff_address=request.dropoff_location,
        dropoff_notes=request.dropoff_notes,
        distance_miles=pricing["distance_miles"],
        vehicle_make=request.vehicle_make,
        vehicle_model=request.vehicle_model,
        vehicle_year=request.vehicle_year,
        vehicle_color=request.vehicle_color,
        license_plate=request.license_plate,
        # NEW FIELDS FROM MIGRATION
        is_awd=request.is_awd,
        is_lowered=request.is_lowered,
        is_damaged=request.is_damaged,
        # PRICING FIELDS
        quoted_price=pricing["customer_price"],
        driver_payout=pricing["driver_payout"],
        platform_fee=pricing["platform_fee"],
        stripe_fee=pricing["stripe_fee"],
        payment_intent_id=payment_intent["payment_intent_id"],
        payment_status=PaymentStatus.AUTHORIZED,
        status=TowStatus.SEARCHING
    )
    
    db.add(tow_request)
    await db.commit()
    await db.refresh(tow_request)
    
    # Find and notify drivers using YOUR existing matching service
    matching_service = MatchingService(db)
    
    # Determine if flatbed is required
    from app.models import ServiceType
    service_result = await db.execute(
        select(ServiceType).where(ServiceType.id == service_type_id)
    )
    service = service_result.scalar_one_or_none()
    requires_flatbed = service.requires_flatbed if service else False
    
    drivers = await matching_service.find_available_drivers(
        pickup_location=(pickup_lat, pickup_lng),
        vehicle_type_id=str(vehicle_type_id),
        requires_flatbed=requires_flatbed
    )
    
    if drivers:
        await matching_service.send_tow_offers(tow_request.id, drivers)
    
    return TowRequestResponse.from_orm(tow_request)
