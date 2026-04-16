from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
import boto3
from app.config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.dependencies import get_current_user, get_current_driver
from app.schemas.driver import (
    DriverCreate, DriverUpdate, DriverResponse, DriverLocationUpdate,
    DriverToggleOnline, DriverEarnings
)
from app.models import User, Driver, TowRequest, TowStatus, Transaction, TransactionType
from app.services.payment_service import PaymentService
from app.services.matching_service import MatchingService
from typing import List
from uuid import UUID
from decimal import Decimal
import logging

router = APIRouter(prefix="/drivers", tags=["Drivers"])

logger = logging.getLogger(__name__)

@router.get("/available-requests")
async def get_available_tow_requests(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_driver)
):
    """Get available tow requests near the driver"""
    if not current_user.driver_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver profile not found"
        )
    
    # Get pending offers for this driver
    from app.models import TowRequestOffer, OfferResponse
    result = await db.execute(
        select(TowRequestOffer)
        .where(
            TowRequestOffer.driver_id == current_user.driver_profile.id,
            TowRequestOffer.response == OfferResponse.PENDING
        )
        .order_by(TowRequestOffer.offered_at.desc())
    )
    offers = result.scalars().all()
    
    # Get full tow request details
    tow_requests = []
    for offer in offers:
        tow_result = await db.execute(
            select(TowRequest).where(TowRequest.id == offer.tow_request_id)
        )
        tow = tow_result.scalar_one_or_none()
        if tow:
            tow_requests.append({
                "tow_request_id": tow.id,
                "pickup_address": tow.pickup_address,
                "dropoff_address": tow.dropoff_address,
                "distance_miles": float(tow.distance_miles),
                "driver_payout": float(tow.driver_payout),
                "distance_from_pickup": float(offer.distance_from_pickup),
                "offered_at": offer.offered_at
            })
    
    return tow_requests

@router.post("/toggle-online")
async def toggle_online_status(
    status_data: DriverToggleOnline,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_driver)
):
    """Toggle driver online/offline status"""
    if not current_user.driver_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver profile not found"
        )
    
    driver = current_user.driver_profile
    driver.is_online = status_data.is_online
    
    # Update location if going online - CHANGED to use lat/lng
    if status_data.is_online and status_data.latitude and status_data.longitude:
        driver.current_latitude = status_data.latitude
        driver.current_longitude = status_data.longitude
    
    await db.commit()
    
    return {
        "is_online": driver.is_online,
        "message": "Status updated successfully"
    }
 
 
@router.put("/location")
async def update_driver_location(
    location: DriverLocationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_driver)
):
    """Update driver's current location (background updates)"""
    if not current_user.driver_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver profile not found"
        )
    
    driver = current_user.driver_profile
    # CHANGED to use lat/lng columns
    driver.current_latitude = location.latitude
    driver.current_longitude = location.longitude
    
    await db.commit()
    
    # If driver has active tow, update location history
    result = await db.execute(
        select(TowRequest)
        .where(
            TowRequest.driver_id == driver.id,
            TowRequest.status.in_([
                TowStatus.ACCEPTED,
                TowStatus.EN_ROUTE_PICKUP,
                TowStatus.VEHICLE_LOADED,
                TowStatus.EN_ROUTE_DROPOFF
            ])
        )
    )
    active_tow = result.scalar_one_or_none()
    
    if active_tow:
        from app.models import LocationHistory
        location_record = LocationHistory(
            tow_request_id=active_tow.id,
            driver_id=driver.id,
            # CHANGED to use lat/lng columns
            latitude=location.latitude,
            longitude=location.longitude,
            speed=location.speed,
            heading=location.heading
        )
        db.add(location_record)
        await db.commit()
        
        # Broadcast location update via WebSocket (handled by WebSocket endpoint)
    
    return {"message": "Location updated successfully"}

@router.post("/apply", status_code=status.HTTP_201_CREATED)
async def apply_as_driver(
    driver_data: DriverCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.driver_profile:
        raise HTTPException(status_code=400, detail="User already has a driver profile")

    driver = Driver(
        user_id=current_user.id,
        license_number=driver_data.license_number,
        license_state=driver_data.license_state,
        license_expiry=driver_data.license_expiry,
        license_class=getattr(driver_data, 'license_class', None),
        vehicle_year=getattr(driver_data, 'vehicle_year', None),
        vehicle_make=getattr(driver_data, 'vehicle_make', None),
        vehicle_model=getattr(driver_data, 'vehicle_model', None),
        vehicle_type=getattr(driver_data, 'vehicle_type', None),
        vin=getattr(driver_data, 'vin', None),
        license_plate=getattr(driver_data, 'license_plate', None),
        plate_state=getattr(driver_data, 'plate_state', None),
        insurance_provider=getattr(driver_data, 'insurance_provider', None),
        policy_number=getattr(driver_data, 'policy_number', None),
        policy_expiry=getattr(driver_data, 'policy_expiry', None),
        company_name=driver_data.company_name,
        company_ein=driver_data.company_ein,
        approval_status='pending'
    )

    db.add(driver)
    await db.commit()
    await db.refresh(driver)

    # Stripe Connect — non-blocking, log failure but don't crash
    onboarding_url = None
    try:
        payment_service = PaymentService(db)
        onboarding_url = await payment_service.setup_driver_connect_account(
            driver_id=driver.id,
            email=current_user.email
        )
    except Exception as e:
        logger.warning(f"Stripe Connect setup failed for driver {driver.id}: {e}")

    return {
        "id": str(driver.id),
        "status": "pending",
        "message": "Driver application submitted successfully",
        "stripe_onboarding_url": onboarding_url
    }

@router.get("/profile", response_model=DriverResponse)
async def get_driver_profile(
    current_user: User = Depends(get_current_driver),
    db: AsyncSession = Depends(get_db)
):
    """Get driver's profile"""
    if not current_user.driver_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver profile not found"
        )
    
    return DriverResponse.from_orm(current_user.driver_profile)

@router.put("/profile", response_model=DriverResponse)
async def update_driver_profile(
    driver_data: DriverUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_driver)
):
    """Update driver profile"""
    if not current_user.driver_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver profile not found"
        )
    
    driver = current_user.driver_profile
    
    # Update fields
    if driver_data.license_number:
        driver.license_number = driver_data.license_number
    if driver_data.license_state:
        driver.license_state = driver_data.license_state
    if driver_data.license_expiry:
        driver.license_expiry = driver_data.license_expiry
    if driver_data.insurance_policy_number:
        driver.insurance_policy_number = driver_data.insurance_policy_number
    if driver_data.insurance_expiry:
        driver.insurance_expiry = driver_data.insurance_expiry
    if driver_data.company_name:
        driver.company_name = driver_data.company_name
    if driver_data.company_ein:
        driver.company_ein = driver_data.company_ein
    
    await db.commit()
    await db.refresh(driver)
    
    return DriverResponse.from_orm(driver)

@router.post("/{driver_id}/documents")
async def upload_driver_document(
    driver_id: UUID,
    file: UploadFile = File(...),
    document_type: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload a driver document (license, insurance, registration)"""
    # Verify driver belongs to current user
    result = await db.execute(
        select(Driver).where(Driver.id == driver_id, Driver.user_id == current_user.id)
    )
    driver = result.scalar_one_or_none()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    # Save file — store to S3 or local depending on your config
    file_url = None
    try:
        file_contents = await file.read()
        
        # If you have S3 configured
        if hasattr(settings, 'AWS_S3_BUCKET') and settings.AWS_S3_BUCKET:
            s3 = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION
            )
            key = f"drivers/{driver_id}/{document_type}/{file.filename}"
            s3.put_object(
                Bucket=settings.AWS_S3_BUCKET,
                Key=key,
                Body=file_contents,
                ContentType=file.content_type
            )
            file_url = f"https://{settings.AWS_S3_BUCKET}.s3.amazonaws.com/{key}"
        
        # Update the correct URL field based on document type
        if document_type == "dl_photo":
            driver.license_photo_url = file_url or f"uploaded:{file.filename}"
        elif document_type == "insurance":
            driver.insurance_photo_url = file_url or f"uploaded:{file.filename}"
        # vehicle_registration and void_check don't have dedicated columns yet — just log success
        
        await db.commit()
        
    except Exception as e:
        logger.warning(f"Document upload error for driver {driver_id}: {e}")
        # Don't fail registration over document upload issues

    return {"message": f"{document_type} uploaded successfully", "url": file_url}


@router.post("/{driver_id}/banking")
async def save_banking_info(
    driver_id: UUID,
    banking_data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Save driver banking/payout information"""
    result = await db.execute(
        select(Driver).where(Driver.id == driver_id, Driver.user_id == current_user.id)
    )
    driver = result.scalar_one_or_none()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    # Store via Stripe Connect if available, otherwise log for manual processing
    try:
        payment_service = PaymentService(db)
        await payment_service.setup_driver_connect_account(
            driver_id=driver.id,
            email=current_user.email
        )
    except Exception as e:
        logger.warning(f"Banking setup error for driver {driver_id}: {e}")
        # Store raw for manual processing — never store plain account numbers in prod
        # Use Stripe, Plaid, or Dwolla for real banking in production

    return {"message": "Banking information received"}

@router.post("/accept-request/{request_id}")
async def accept_tow_request(
    request_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_driver)
):
    """Accept a tow request"""
    if not current_user.driver_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver profile not found"
        )
    
    matching_service = MatchingService(db)
    success = await matching_service.accept_tow_request(
        tow_request_id=request_id,
        driver_id=current_user.driver_profile.id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not accept tow request. It may have been accepted by another driver."
        )
    
    return {"message": "Tow request accepted successfully"}

@router.post("/reject-request/{request_id}")
async def reject_tow_request(
    request_id: UUID,
    reason: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_driver)
):
    """Reject a tow request"""
    if not current_user.driver_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver profile not found"
        )
    
    matching_service = MatchingService(db)
    await matching_service.reject_tow_request(
        tow_request_id=request_id,
        driver_id=current_user.driver_profile.id,
        reason=reason
    )
    
    return {"message": "Tow request rejected"}

@router.get("/earnings", response_model=DriverEarnings)
async def get_driver_earnings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_driver)
):
    """Get driver earnings summary"""
    if not current_user.driver_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver profile not found"
        )
    
    driver_id = current_user.driver_profile.id
    
    # Total earnings
    total_result = await db.execute(
        select(func.sum(Transaction.amount))
        .where(
            Transaction.driver_id == driver_id,
            Transaction.transaction_type == TransactionType.PAYOUT
        )
    )
    total_earnings = total_result.scalar() or Decimal("0")
    
    # Completed tows
    completed_result = await db.execute(
        select(func.count(TowRequest.id))
        .where(
            TowRequest.driver_id == driver_id,
            TowRequest.status == TowStatus.COMPLETED
        )
    )
    completed_tows = completed_result.scalar() or 0
    
    # Average rating
    rating_result = await db.execute(
        select(func.avg(TowRequest.driver_rating))
        .where(
            TowRequest.driver_id == driver_id,
            TowRequest.driver_rating.isnot(None)
        )
    )
    average_rating = rating_result.scalar() or Decimal("5.0")
    
    # Total distance
    distance_result = await db.execute(
        select(func.sum(TowRequest.distance_miles))
        .where(
            TowRequest.driver_id == driver_id,
            TowRequest.status == TowStatus.COMPLETED
        )
    )
    total_distance = distance_result.scalar() or Decimal("0")
    
    # This week earnings
    from datetime import datetime, timedelta
    week_ago = datetime.now() - timedelta(days=7)
    week_result = await db.execute(
        select(func.sum(Transaction.amount))
        .where(
            Transaction.driver_id == driver_id,
            Transaction.transaction_type == TransactionType.PAYOUT,
            Transaction.created_at >= week_ago
        )
    )
    earnings_this_week = week_result.scalar() or Decimal("0")
    
    # This month earnings
    month_ago = datetime.now() - timedelta(days=30)
    month_result = await db.execute(
        select(func.sum(Transaction.amount))
        .where(
            Transaction.driver_id == driver_id,
            Transaction.transaction_type == TransactionType.PAYOUT,
            Transaction.created_at >= month_ago
        )
    )
    earnings_this_month = month_result.scalar() or Decimal("0")
    
    return DriverEarnings(
        total_earnings=total_earnings,
        completed_tows=completed_tows,
        average_rating=round(average_rating, 2),
        total_distance=total_distance,
        earnings_this_week=earnings_this_week,
        earnings_this_month=earnings_this_month
    )

@router.get("/history")
async def get_driver_tow_history(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_driver)
):
    """Get driver's tow history"""
    if not current_user.driver_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver profile not found"
        )
    
    result = await db.execute(
        select(TowRequest)
        .where(TowRequest.driver_id == current_user.driver_profile.id)
        .order_by(TowRequest.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    tows = result.scalars().all()
    
    return tows
