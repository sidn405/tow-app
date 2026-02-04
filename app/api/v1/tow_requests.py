from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.dependencies import get_current_user, get_current_customer, get_current_driver
from app.schemas.tow_request import (
    TowQuoteRequest, TowQuoteResponse, TowRequestCreate,
    TowRequestResponse, TowStatusUpdate, TowRating, TowCancellation
)
from app.services.pricing_service import PricingService
from app.services.matching_service import MatchingService
from app.services.payment_service import PaymentService
from app.services.notification_service import NotificationService
from app.models import User, TowRequest, TowStatus, PaymentStatus
from app.utils.geo import calculate_distance
from typing import List
from uuid import UUID

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
    from geoalchemy2.elements import WKTElement
    tow_request = TowRequest(
        customer_id=current_user.id,
        service_type_id=tow_data.service_type_id,
        vehicle_type_id=tow_data.vehicle_type_id,
        tow_reason_id=tow_data.tow_reason_id,
        pickup_location=WKTElement(f"POINT({tow_data.pickup_location.longitude} {tow_data.pickup_location.latitude})", srid=4326),
        pickup_address=tow_data.pickup_address,
        pickup_notes=tow_data.pickup_notes,
        dropoff_location=WKTElement(f"POINT({tow_data.dropoff_location.longitude} {tow_data.dropoff_location.latitude})", srid=4326),
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
        await payment_service.capture_payment(tow_id)
    
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

@router.get("/customer/history", response_model=List[TowRequestResponse])
async def get_customer_tow_history(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_customer)
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
    return [TowRequestResponse.from_orm(tow) for tow in tows]

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
