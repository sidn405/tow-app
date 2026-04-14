from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.database import get_db

from app.api.v1.auth import get_current_user
from app.dependencies import get_current_user, get_current_customer, get_current_driver
from app.schemas.tow_request import (
    TowQuoteRequest, TowQuoteResponse, TowRequestCreate,
    TowRequestResponse, TowStatusUpdate, TowRating, TowCancellation
)
import stripe
from app.services.pricing_service import PricingService
from app.services.matching_service import MatchingService
from app.services.payment_service import PaymentService
from app.services.notification_service import NotificationService
from app.services.email_service import EmailService
from app.models import User, TowRequest, TowStatus, PaymentStatus
from app.utils.geo import calculate_distance
from typing import List
from uuid import UUID

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import uuid

class SimpleTowRequest(BaseModel):
    """Frontend sends simple string data"""
    vehicle_year: int = Field(..., ge=1900, le=2026)
    vehicle_make: str
    vehicle_model: str
    vehicle_type: str  # sedan, luxury, exotic, etc.
    is_awd: bool = False
    is_lowered: bool = False
    is_damaged: bool = False
    pickup_location: str
    pickup_lat: float
    pickup_lng: float
    dropoff_location: str
    dropoff_lat: float
    dropoff_lng: float
    reason: str
    vehicle_color: Optional[str] = None
    license_plate: Optional[str] = None
    pickup_notes: Optional[str] = None  # ← Add this
    dropoff_notes: Optional[str] = None  # ← Add this

router = APIRouter(prefix="/tows", tags=["Tow Requests"])

@router.post("/quote", response_model=TowQuoteResponse)
async def get_tow_quote(
    quote_request: TowQuoteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get price quote for a tow request"""
    # Calculate distance
    distance = calculate_distance(
        (quote_request.pickup_location.latitude, quote_request.pickup_location.longitude),
        (quote_request.dropoff_location.latitude, quote_request.dropoff_location.longitude)
    )
    
    # Get pricing
    pricing_service = PricingService(db)
    pricing = await pricing_service.calculate_tow_price(
        distance_miles=distance,
        service_type_id=str(quote_request.service_type_id),
        vehicle_type_id=str(quote_request.vehicle_type_id),
        tow_reason_id=str(quote_request.tow_reason_id)
    )
    
    return TowQuoteResponse(**pricing)

@router.post("/request-simple")
async def create_simple_tow_request(
    request: SimpleTowRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create tow request from simple frontend format and save to database.
    """
    from app.services.tow_request_mapper import TowRequestMapper
    
    try:
        # Step 1: Convert simple format to database format
        mapper = TowRequestMapper(db)
        mapped_data = await mapper.map_request(request.dict())
        
        # Step 2: Calculate distance
        distance_miles = calculate_distance(
            request.pickup_lat, request.pickup_lng,
            request.dropoff_lat, request.dropoff_lng
        )
        
        # Step 3: Calculate pricing
        try:
            pricing_service = PricingService(db)
            pricing = await pricing_service.calculate_tow_price(
                distance_miles=distance_miles,
                service_type_id=mapped_data["service_type_id"],
                vehicle_type_id=mapped_data["vehicle_type_id"],
                tow_reason_id=mapped_data["tow_reason_id"]
            )
        except Exception as e:
            print(f"PRICING ERROR: {str(e)}")
            print(f"PRICING ERROR TYPE: {type(e)}")
            import traceback
            traceback.print_exc()
            raise
        
        # Step 4: Create TowRequest record
        tow_request = TowRequest(
            id=uuid.uuid4(),
            customer_id=current_user.id,
            
            # Vehicle details
            vehicle_year=request.vehicle_year,
            vehicle_make=request.vehicle_make,
            vehicle_model=request.vehicle_model,
            vehicle_color=request.vehicle_color,
            license_plate=request.license_plate,
            
            # Special requirements
            is_awd=request.is_awd,
            is_lowered=request.is_lowered,
            is_damaged=request.is_damaged,
            
            # Lookup table references
            service_type_id=mapped_data.get("service_type_id"),
            vehicle_type_id=mapped_data.get("vehicle_type_id"),
            tow_reason_id=mapped_data.get("tow_reason_id"),
            
            # Location details - CHANGED to use lat/lng
            pickup_latitude=request.pickup_lat,
            pickup_longitude=request.pickup_lng,
            pickup_address=request.pickup_location,
            pickup_notes=request.pickup_notes,
            dropoff_latitude=request.dropoff_lat,
            dropoff_longitude=request.dropoff_lng,
            dropoff_address=request.dropoff_location,
            dropoff_notes=request.dropoff_notes,
            distance_miles=distance_miles,
            
            # Pricing
            quoted_price=pricing["customer_price"],
            driver_payout=pricing["driver_payout"],
            platform_fee=pricing["platform_fee"],
            stripe_fee=pricing["stripe_fee"],
            
            # Status
            status=TowStatus.PENDING,
            payment_status=PaymentStatus.PENDING,
            requested_at=datetime.utcnow(),
        )
        
        # Step 5: Save to database
        db.add(tow_request)
        await db.commit()
        await db.refresh(tow_request)
        
        # CHARGE CUSTOMER using your PaymentService
        payment_service = PaymentService(db)
        
        if current_user.stripe_customer_id:
            try:
                # Charge immediately using saved payment method
                payment_intent = stripe.PaymentIntent.create(
                    amount=int(pricing["customer_price"] * 100),
                    currency='usd',
                    customer=current_user.stripe_customer_id,
                    payment_method=current_user.default_payment_method_id,
                    off_session=True,
                    confirm=True,
                    capture_method='manual',  # ← ONLY AUTHORIZE, DON'T CAPTURE YET
                    description=f"Tow authorization: {request.pickup_location} → {request.dropoff_location}",
                    metadata={
                        'tow_request_id': str(tow_request.id),
                        'customer_email': current_user.email,
                        'vehicle': f"{request.vehicle_year} {request.vehicle_make} {request.vehicle_model}"
                    }
                )

                if payment_intent.status == 'requires_capture':
                    tow_request.payment_intent_id = payment_intent.id
                    tow_request.payment_status = PaymentStatus.AUTHORIZED  # ← Changed from CAPTURED
                    await db.commit()
                else:
                    raise HTTPException(400, "Payment authorization failed")
                    
            except stripe.error.CardError as e:
                tow_request.payment_status = PaymentStatus.FAILED
                await db.commit()
                raise HTTPException(400, f"Card declined: {e.user_message}")
        else:
            raise HTTPException(400, "No payment method on file")
        
        # Step 6: Return success response
        return {
            "success": True,
            "message": "Tow request created! Payment authorized (you'll be charged when tow completes)",
            "request_id": str(tow_request.id),
            "estimated_price": float(pricing["customer_price"]),
            "payment_status": "authorized",
            "distance_miles": float(distance_miles),
            "service_type": "flatbed" if request.is_awd or request.is_lowered else "standard"
            
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating tow request: {str(e)}")
 
 
def calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calculate distance between two points using Haversine formula.
    Returns distance in miles.
    """
    from math import radians, sin, cos, sqrt, atan2
    
    # Earth's radius in miles
    R = 3959.0
    
    # Convert to radians
    lat1_rad = radians(lat1)
    lng1_rad = radians(lng1)
    lat2_rad = radians(lat2)
    lng2_rad = radians(lng2)
    
    # Haversine formula
    dlat = lat2_rad - lat1_rad
    dlng = lng2_rad - lng1_rad
    
    a = sin(dlat / 2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlng / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    
    distance = R * c
    return round(distance, 2)
 
 
def calculate_pricing(
    distance_miles: float,
    vehicle_type: str,
    service_type: str,
    is_awd: bool = False,
    is_lowered: bool = False,
    is_damaged: bool = False
) -> dict:
    """
    Calculate pricing for tow request.
    
    TODO: Replace this with your actual PricingService logic.
    This is a simplified version for now.
    """
    # Base rates
    base_rate = 75.00
    per_mile_rate = 3.50
    
    # Vehicle type multipliers
    vehicle_multipliers = {
        "sedan": 1.0,
        "suv": 1.2,
        "truck": 1.3,
        "van": 1.2,
        "luxury": 1.5,
        "exotic": 2.0,
        "motorcycle": 0.8,
        "rv": 1.8,
        "large_truck": 2.5
    }
    
    # Service type adjustments
    service_adjustments = {
        "standard_tow": 0,
        "flatbed_tow": 25,
        "motorcycle_tow": -10,
        "heavy_duty_tow": 50
    }
    
    # Calculate base price
    multiplier = vehicle_multipliers.get(vehicle_type.lower(), 1.0)
    distance_charge = distance_miles * per_mile_rate
    subtotal = (base_rate + distance_charge) * multiplier
    
    # Add service type adjustment
    # Note: We need to look up the actual service type name from the UUID
    # For now, estimate based on vehicle requirements
    if is_awd or is_lowered or is_damaged or vehicle_type in ["exotic", "luxury"]:
        subtotal += 25  # Flatbed surcharge
    
    # Platform fee (15%)
    platform_fee = subtotal * 0.15
    
    # Stripe fee (2.9% + $0.30)
    stripe_fee = (subtotal * 0.029) + 0.30
    
    # Total price to customer
    total_price = subtotal + platform_fee + stripe_fee
    
    # Driver payout (85% of subtotal)
    driver_payout = subtotal * 0.85
    
    return {
        "total_price": round(total_price, 2),
        "driver_payout": round(driver_payout, 2),
        "platform_fee": round(platform_fee, 2),
        "stripe_fee": round(stripe_fee, 2),
        "distance_charge": round(distance_charge, 2),
        "base_rate": base_rate
    }

@router.post("/", response_model=TowRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_tow_request(
    tow_data: TowRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_customer)
):
    """Create a new tow request"""
    # Calculate distance
    distance = calculate_distance(
        (tow_data.pickup_location.latitude, tow_data.pickup_location.longitude),
        (tow_data.dropoff_location.latitude, tow_data.dropoff_location.longitude)
    )
    
    # Get pricing
    pricing_service = PricingService(db)
    pricing = await pricing_service.calculate_tow_price(
        distance_miles=distance,
        service_type_id=str(tow_data.service_type_id),
        vehicle_type_id=str(tow_data.vehicle_type_id),
        tow_reason_id=str(tow_data.tow_reason_id)
    )
    
    # Create payment intent
    payment_service = PaymentService(db)
    payment_intent = await payment_service.create_payment_intent(
        tow_request_id=None,  # Will update after creating tow request
        customer_id=current_user.id,
        amount=pricing["customer_price"]
    )
    
    # Create tow request
    tow_request = TowRequest(
        customer_id=current_user.id,
        service_type_id=tow_data.service_type_id,
        vehicle_type_id=tow_data.vehicle_type_id,
        tow_reason_id=tow_data.tow_reason_id,
        pickup_latitude=tow_data.pickup_location.latitude,
        pickup_longitude=tow_data.pickup_location.longitude,
        pickup_address=tow_data.pickup_address,
        pickup_notes=tow_data.pickup_notes,
        dropoff_latitude=tow_data.dropoff_location.latitude,
        dropoff_longitude=tow_data.dropoff_location.longitude,
        dropoff_address=tow_data.dropoff_address,
        dropoff_notes=tow_data.dropoff_notes,
        distance_miles=pricing["distance_miles"],
        vehicle_make=tow_data.vehicle_make,
        vehicle_model=tow_data.vehicle_model,
        vehicle_year=tow_data.vehicle_year,
        vehicle_color=tow_data.vehicle_color,
        license_plate=tow_data.license_plate,
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
    
    # Find and notify drivers
    matching_service = MatchingService(db)
    drivers = await matching_service.find_available_drivers(
        pickup_location=(tow_data.pickup_location.latitude, tow_data.pickup_location.longitude),
        vehicle_type_id=str(tow_data.vehicle_type_id),
        requires_flatbed=False  # Would get this from tow_reason
    )
    
    if drivers:
        await matching_service.send_tow_offers(tow_request.id, drivers)
    
    return TowRequestResponse.from_orm(tow_request)

@router.get("/{tow_id}", response_model=TowRequestResponse)
async def get_tow_request(
    tow_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get tow request details"""
    result = await db.execute(
        select(TowRequest).where(TowRequest.id == tow_id)
    )
    tow_request = result.scalar_one_or_none()
    
    if not tow_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tow request not found"
        )
    
    # Check authorization
    if tow_request.customer_id != current_user.id and \
       (not current_user.driver_profile or tow_request.driver_id != current_user.driver_profile.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this tow request"
        )
    
    return TowRequestResponse.from_orm(tow_request)

@router.put("/{tow_id}/status")
async def update_tow_status(
    tow_id: UUID,
    status_update: TowStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_driver)
):
    """Update tow request status (driver only)"""
    result = await db.execute(
        select(TowRequest).where(TowRequest.id == tow_id)
    )
    tow_request = result.scalar_one_or_none()
    
    if not tow_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tow request not found"
        )
    
    # Check if driver is assigned to this tow
    if not current_user.driver_profile or tow_request.driver_id != current_user.driver_profile.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this tow request"
        )
    
    # Update status and timestamps
    from datetime import datetime
    from app.models import Driver
    tow_request.status = status_update.status
    
    if status_update.status == TowStatus.EN_ROUTE_PICKUP:
        pass  # No specific timestamp
    elif status_update.status == TowStatus.ARRIVED_PICKUP:
        tow_request.arrived_pickup_at = datetime.utcnow()
    elif status_update.status == TowStatus.VEHICLE_LOADED:
        tow_request.loaded_at = datetime.utcnow()
    elif status_update.status == TowStatus.ARRIVED_DROPOFF:
        tow_request.arrived_dropoff_at = datetime.utcnow()
    elif status_update.status == TowStatus.COMPLETED:
        tow_request.completed_at = datetime.utcnow()
        # Capture payment
        payment_service = PaymentService(db)
        payment_captured = await payment_service.capture_payment(tow_id)
        
        if payment_captured:
                # Get customer info
                customer_result = await db.execute(
                    select(User).where(User.id == tow_request.customer_id)
                )
                customer = customer_result.scalar_one_or_none()
                
                # Get driver info
                driver_result = await db.execute(
                    select(Driver).where(Driver.id == tow_request.driver_id)
                )
                driver = driver_result.scalar_one_or_none()
                
                # Send receipt email
                if customer:
                    tow_data = {
                        'id': str(tow_request.id),
                        'completed_at': tow_request.completed_at,
                        'vehicle_year': tow_request.vehicle_year,
                        'vehicle_make': tow_request.vehicle_make,
                        'vehicle_model': tow_request.vehicle_model,
                        'pickup_address': tow_request.pickup_address,
                        'dropoff_address': tow_request.dropoff_address,
                        'distance_miles': tow_request.distance_miles,
                        'quoted_price': tow_request.quoted_price,
                        'platform_fee': tow_request.platform_fee,
                        'stripe_fee': tow_request.stripe_fee,
                        'driver_name': driver.user.name if driver and driver.user else 'Your Driver',
                        'card_last4': '****'  # TODO: Get from Stripe
                    }
                    
                    await EmailService.send_receipt_email(
                        customer_email=customer.email,
                        customer_name=customer.name,
                        tow_data=tow_data
                    )
        
        await db.commit()
    
    # Notify customer
    notification_service = NotificationService(db)
    await notification_service.notify_status_update(
        user_id=tow_request.customer_id,
        tow_request_id=tow_id,
        status=status_update.status.value,
        message=f"Your tow status has been updated to: {status_update.status.value}"
    )
    
    return {"message": "Status updated successfully"}

@router.post("/{tow_id}/cancel")
async def cancel_tow_request(
    tow_id: UUID,
    cancellation: TowCancellation,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Cancel a tow request"""
    result = await db.execute(
        select(TowRequest).where(TowRequest.id == tow_id)
    )
    tow_request = result.scalar_one_or_none()
    
    if not tow_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tow request not found"
        )
    
    # Check authorization
    if tow_request.customer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to cancel this tow request"
        )
    
    # Check if can be cancelled
    if tow_request.status in [TowStatus.COMPLETED, TowStatus.CANCELLED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel completed or already cancelled tow"
        )
    
    # Update status
    from datetime import datetime
    tow_request.status = TowStatus.CANCELLED
    tow_request.cancelled_at = datetime.utcnow()
    tow_request.cancellation_reason = cancellation.reason
    
    # Process refund
    payment_service = PaymentService(db)
    await payment_service.refund_payment(tow_id, cancellation.reason)
    
    await db.commit()
    
    # Notify driver if assigned
    if tow_request.driver_id:
        notification_service = NotificationService(db)
        await notification_service.notify_status_update(
            user_id=tow_request.driver_id,
            tow_request_id=tow_id,
            status="cancelled",
            message="The customer has cancelled the tow request"
        )
    
    return {"message": "Tow request cancelled successfully"}

@router.post("/{tow_id}/rate")
async def rate_tow(
    tow_id: UUID,
    rating: TowRating,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Rate completed tow (customer rates driver or driver rates customer)"""
    result = await db.execute(
        select(TowRequest).where(TowRequest.id == tow_id)
    )
    tow_request = result.scalar_one_or_none()
    
    if not tow_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tow request not found"
        )
    
    if tow_request.status != TowStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only rate completed tows"
        )
    
    # Determine who is rating
    if tow_request.customer_id == current_user.id:
        # Customer rating driver
        tow_request.driver_rating = rating.rating
        tow_request.driver_review = rating.review
        
        # Update driver's overall rating
        from app.models import Driver
        if tow_request.driver_id:
            driver_result = await db.execute(
                select(Driver).where(Driver.id == tow_request.driver_id)
            )
            driver = driver_result.scalar_one_or_none()
            if driver:
                # Recalculate average rating
                from sqlalchemy import func
                avg_result = await db.execute(
                    select(func.avg(TowRequest.driver_rating)).where(
                        TowRequest.driver_id == driver.id,
                        TowRequest.driver_rating.isnot(None)
                    )
                )
                avg_rating = avg_result.scalar()
                if avg_rating:
                    driver.rating = round(float(avg_rating), 2)
    
    elif current_user.driver_profile and tow_request.driver_id == current_user.driver_profile.id:
        # Driver rating customer
        tow_request.customer_rating = rating.rating
        tow_request.customer_review = rating.review
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to rate this tow"
        )
    
    await db.commit()
    return {"message": "Rating submitted successfully"}

@router.get("/customer/history")  # Remove response_model for now
async def get_customer_tow_history(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)  # ← Use get_current_user instead
):
    """Get customer's tow history"""
    result = await db.execute(
        select(TowRequest)
        .where(TowRequest.customer_id == current_user.id)
        .order_by(TowRequest.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    tows = result.scalars().all()
    
    # Return as dict instead of complex response model
    return [{
        "id": str(tow.id),
        "vehicle_year": tow.vehicle_year,
        "vehicle_make": tow.vehicle_make,
        "vehicle_model": tow.vehicle_model,
        "pickup_address": tow.pickup_address,
        "dropoff_address": tow.dropoff_address,
        "quoted_price": float(tow.quoted_price),
        "distance_miles": float(tow.distance_miles),
        "status": tow.status,
        "payment_status": tow.payment_status,
        "created_at": tow.created_at.isoformat()
    } for tow in tows]

@router.get("/driver/active")
async def get_driver_active_tow(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_driver)
):
    """Get driver's currently active tow"""
    if not current_user.driver_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver profile not found"
        )
    
    result = await db.execute(
        select(TowRequest)
        .where(
            TowRequest.driver_id == current_user.driver_profile.id,
            TowRequest.status.in_([
                TowStatus.ACCEPTED,
                TowStatus.EN_ROUTE_PICKUP,
                TowStatus.ARRIVED_PICKUP,
                TowStatus.VEHICLE_LOADED,
                TowStatus.EN_ROUTE_DROPOFF,
                TowStatus.ARRIVED_DROPOFF
            ])
        )
        .order_by(TowRequest.created_at.desc())
    )
    tow = result.scalar_one_or_none()
    
    if not tow:
        return None
    
    return TowRequestResponse.from_orm(tow)

@router.get("/{tow_id}/tracking")
async def get_tow_tracking(
    tow_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get real-time tracking info for active tow"""
    
    # Get tow request
    result = await db.execute(
        select(TowRequest).where(TowRequest.id == tow_id)
    )
    tow = result.scalar_one_or_none()
    
    if not tow:
        raise HTTPException(404, "Tow request not found")
    
    # Verify authorization
    if tow.customer_id != current_user.id:
        raise HTTPException(403, "Not authorized")
    
    from app.models import Driver
    
    # Get driver's current location
    if tow.driver_id:
        driver_result = await db.execute(
            select(Driver).where(Driver.id == tow.driver_id)
        )
        driver = driver_result.scalar_one_or_none()
        
        if driver:
            return {
                "tow_id": str(tow.id),
                "status": tow.status,
                "driver_location": {
                    "latitude": float(driver.current_latitude) if driver.current_latitude else None,
                    "longitude": float(driver.current_longitude) if driver.current_longitude else None,
                    "updated_at": driver.updated_at
                },
                "pickup_location": {
                    "latitude": float(tow.pickup_latitude),
                    "longitude": float(tow.pickup_longitude),
                    "address": tow.pickup_address
                },
                "dropoff_location": {
                    "latitude": float(tow.dropoff_latitude),
                    "longitude": float(tow.dropoff_longitude),
                    "address": tow.dropoff_address
                },
                "driver_info": {
                    "name": driver.user.name if driver.user else "Driver",
                    "rating": float(driver.rating) if driver.rating else None
                },
                "estimated_arrival": None  # TODO: Calculate ETA
            }
    
    return {
        "tow_id": str(tow.id),
        "status": tow.status,
        "message": "Driver not yet assigned"
    }
