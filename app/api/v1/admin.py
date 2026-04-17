from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User, Driver, TowRequest, TowStatus, UserRole, Transaction, TransactionType
from app.models import ApprovalStatus
from typing import List, Optional
from uuid import UUID
from decimal import Decimal
from datetime import datetime, timedelta
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])


# ──────────────────────────────────────────
# SCHEMAS
# ──────────────────────────────────────────

class DriverStatusUpdate(BaseModel):
    approval_status: str  # pending | approved | rejected | suspended
    reason: Optional[str] = None

class UserStatusUpdate(BaseModel):
    is_active: bool


# ──────────────────────────────────────────
# DEPENDENCY — Admin guard
# ──────────────────────────────────────────

async def get_current_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """Only allow users with ADMIN role"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


# ──────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────

def serialize_user(u: User) -> dict:
    if not u:
        return {}
    return {
        "id": str(u.id),
        "first_name": u.first_name,
        "last_name": u.last_name,
        "email": u.email,
        "phone": u.phone,
        "role": u.role.value if u.role else None,
        "is_active": u.is_active,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }

def serialize_driver(d: Driver) -> dict:
    if not d:
        return {}
    return {
        "id": str(d.id),
        "user_id": str(d.user_id),
        "user": serialize_user(d.user) if d.user else None,

        # License
        "license_number": d.license_number,
        "license_state": d.license_state,
        "license_expiry": d.license_expiry.isoformat() if d.license_expiry else None,
        "license_photo_url": d.license_photo_url,
        "license_class": d.license_class,
        "cdl_endorsements": d.cdl_endorsements or [],
        "towing_experience_years": d.towing_experience_years,

        # Vehicle
        "vehicle_year": d.vehicle_year,
        "vehicle_make": d.vehicle_make,
        "vehicle_model": d.vehicle_model,
        "vehicle_type": d.vehicle_type,
        "vin": d.vin,
        "license_plate": d.license_plate,
        "plate_state": d.plate_state,
        "tow_capacity_lbs": d.tow_capacity_lbs,
        "awd_capable": d.awd_capable,
        "special_considerations": d.special_considerations,

        # Insurance
        "insurance_policy_number": d.insurance_policy_number,
        "insurance_expiry": d.insurance_expiry.isoformat() if d.insurance_expiry else None,
        "insurance_photo_url": d.insurance_photo_url,
        "insurance_provider": d.insurance_provider,
        "policy_number": d.policy_number,
        "policy_effective": d.policy_effective.isoformat() if d.policy_effective else None,
        "policy_expiry": d.policy_expiry.isoformat() if d.policy_expiry else None,

        # Status & metrics
        "approval_status": d.approval_status.value if d.approval_status else None,
        "background_check_status": d.background_check_status.value if d.background_check_status else None,
        "is_online": d.is_online,
        "rating": float(d.rating) if d.rating else 5.0,
        "total_tows": d.total_tows or 0,
        "commission_rate": float(d.commission_rate) if d.commission_rate else 15.0,
        "bank_account_id": d.bank_account_id,
        "company_name": d.company_name,
        "company_ein": d.company_ein,

        "created_at": d.created_at.isoformat() if d.created_at else None,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
    }

def serialize_tow(t: TowRequest) -> dict:
    if not t:
        return {}
    return {
        "id": str(t.id),
        "status": t.status.value if t.status else None,
        "pickup_address": t.pickup_address,
        "dropoff_address": t.dropoff_address,
        "distance_miles": float(t.distance_miles) if t.distance_miles else None,
        "quoted_price": float(t.quoted_price) if t.quoted_price else None,
        "final_price": float(t.final_price) if getattr(t, 'final_price', None) else None,
        "driver_payout": float(t.driver_payout) if t.driver_payout else None,
        "platform_fee": float(t.platform_fee) if t.platform_fee else None,
        "stripe_fee": float(t.stripe_fee) if t.stripe_fee else None,
        "payment_status": t.payment_status.value if t.payment_status else None,
        "vehicle": f"{t.vehicle_year or ''} {t.vehicle_make or ''} {t.vehicle_model or ''}".strip() or None,
        "vehicle_color": t.vehicle_color,
        "license_plate": t.license_plate,
        "customer": serialize_user(t.customer) if hasattr(t, 'customer') and t.customer else None,
        "driver": serialize_driver(t.driver) if hasattr(t, 'driver') and t.driver else None,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


# ──────────────────────────────────────────
# STATS / OVERVIEW
# ──────────────────────────────────────────

@router.get("/stats")
async def get_admin_stats(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Platform-wide statistics for the admin dashboard"""

    # Driver counts
    driver_result = await db.execute(select(func.count(Driver.id)))
    total_drivers = driver_result.scalar() or 0

    online_result = await db.execute(
        select(func.count(Driver.id)).where(Driver.is_online == True)
    )
    online_drivers = online_result.scalar() or 0

    pending_result = await db.execute(
        select(func.count(Driver.id)).where(Driver.approval_status == ApprovalStatus.PENDING)
    )
    pending_drivers = pending_result.scalar() or 0

    # Customer counts
    customer_result = await db.execute(
        select(func.count(User.id)).where(User.role == UserRole.CUSTOMER)
    )
    total_customers = customer_result.scalar() or 0

    # Active tows
    active_statuses = [
        TowStatus.PENDING,
        TowStatus.ACCEPTED,
        TowStatus.EN_ROUTE_PICKUP,
        TowStatus.VEHICLE_LOADED,
        TowStatus.EN_ROUTE_DROPOFF,
    ]
    active_result = await db.execute(
        select(func.count(TowRequest.id)).where(TowRequest.status.in_(active_statuses))
    )
    active_tows = active_result.scalar() or 0

    # Today completed
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    completed_today_result = await db.execute(
        select(func.count(TowRequest.id)).where(
            TowRequest.status == TowStatus.COMPLETED,
            TowRequest.updated_at >= today_start
        )
    )
    completed_today = completed_today_result.scalar() or 0

    # Revenue MTD
    month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    revenue_result = await db.execute(
        select(func.sum(TowRequest.final_price)).where(
            TowRequest.status == TowStatus.COMPLETED,
            TowRequest.updated_at >= month_start
        )
    )
    revenue_mtd = float(revenue_result.scalar() or 0)

    return {
        "total_drivers": total_drivers,
        "online_drivers": online_drivers,
        "pending_drivers": pending_drivers,
        "total_customers": total_customers,
        "active_tows": active_tows,
        "completed_today": completed_today,
        "revenue_mtd": revenue_mtd,
    }


# ──────────────────────────────────────────
# DRIVERS
# ──────────────────────────────────────────

@router.get("/drivers")
async def get_all_drivers(
    status_filter: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Get all drivers with user info eagerly loaded"""
    query = (
        select(Driver)
        .options(selectinload(Driver.user))
        .order_by(Driver.created_at.desc())
        .offset(skip)
        .limit(limit)
    )

    if status_filter:
        query = query.where(Driver.approval_status == status_filter)

    result = await db.execute(query)
    drivers = result.scalars().all()

    return [serialize_driver(d) for d in drivers]


@router.get("/drivers/{driver_id}")
async def get_driver_detail(
    driver_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Get full driver profile including user, tow history"""
    result = await db.execute(
        select(Driver)
        .options(selectinload(Driver.user))
        .where(Driver.id == driver_id)
    )
    driver = result.scalar_one_or_none()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    # Tow history count
    tow_result = await db.execute(
        select(func.count(TowRequest.id)).where(TowRequest.driver_id == driver_id)
    )
    tow_count = tow_result.scalar() or 0

    data = serialize_driver(driver)
    data["tow_history_count"] = tow_count
    return data


@router.put("/drivers/{driver_id}/status")
async def update_driver_status(
    driver_id: UUID,
    update: DriverStatusUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Approve, reject, or suspend a driver"""
    result = await db.execute(
        select(Driver)
        .options(selectinload(Driver.user))
        .where(Driver.id == driver_id)
    )
    driver = result.scalar_one_or_none()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    # Validate status value
    valid_statuses = ["pending", "approved", "rejected", "suspended"]
    if update.approval_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")

    old_status = driver.approval_status
    driver.approval_status = update.approval_status

    # If suspending, take offline immediately
    if update.approval_status == "suspended":
        driver.is_online = False

    await db.commit()

    logger.info(
        f"Admin {admin.email} changed driver {driver_id} status: "
        f"{old_status} → {update.approval_status}"
        + (f" | Reason: {update.reason}" if update.reason else "")
    )

    # TODO: Send notification email to driver here
    # await notify_driver_status_change(driver, update.approval_status, update.reason)

    return {
        "id": str(driver_id),
        "approval_status": update.approval_status,
        "message": f"Driver status updated to {update.approval_status}"
    }


@router.delete("/drivers/{driver_id}")
async def delete_driver(
    driver_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Permanently delete a driver profile (not the user account)"""
    result = await db.execute(select(Driver).where(Driver.id == driver_id))
    driver = result.scalar_one_or_none()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    await db.delete(driver)
    await db.commit()

    logger.info(f"Admin {admin.email} deleted driver profile {driver_id}")
    return {"message": "Driver profile deleted"}


# ──────────────────────────────────────────
# CUSTOMERS / USERS
# ──────────────────────────────────────────

@router.get("/customers")
async def get_all_customers(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Get all customers"""
    result = await db.execute(
        select(User)
        .where(User.role == UserRole.CUSTOMER)
        .order_by(User.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    customers = result.scalars().all()
    return [serialize_user(c) for c in customers]


@router.get("/users")
async def get_all_users(
    role: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Get all users, optionally filtered by role"""
    query = select(User).order_by(User.created_at.desc()).offset(skip).limit(limit)
    if role:
        query = query.where(User.role == role)

    result = await db.execute(query)
    users = result.scalars().all()
    return [serialize_user(u) for u in users]


@router.put("/users/{user_id}/status")
async def update_user_status(
    user_id: UUID,
    update: UserStatusUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Activate or suspend any user account"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = update.is_active
    await db.commit()

    logger.info(f"Admin {admin.email} set user {user_id} is_active={update.is_active}")
    return {
        "id": str(user_id),
        "is_active": update.is_active,
        "message": f"User {'activated' if update.is_active else 'suspended'}"
    }


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Permanently delete a user and cascade to driver profile"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await db.delete(user)
    await db.commit()

    logger.info(f"Admin {admin.email} deleted user {user_id}")
    return {"message": "User deleted"}


# ──────────────────────────────────────────
# TOW REQUESTS
# ──────────────────────────────────────────

@router.get("/tows")
async def get_all_tows(
    status_filter: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Get all tow requests with customer and driver info"""
    query = (
        select(TowRequest)
        .options(
            selectinload(TowRequest.customer),
            selectinload(TowRequest.driver).selectinload(Driver.user)
        )
        .order_by(TowRequest.created_at.desc())
        .offset(skip)
        .limit(limit)
    )

    if status_filter:
        query = query.where(TowRequest.status == status_filter)

    result = await db.execute(query)
    tows = result.scalars().all()
    return [serialize_tow(t) for t in tows]


@router.get("/tows/{tow_id}")
async def get_tow_detail(
    tow_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Get full tow request details"""
    result = await db.execute(
        select(TowRequest)
        .options(
            selectinload(TowRequest.customer),
            selectinload(TowRequest.driver).selectinload(Driver.user)
        )
        .where(TowRequest.id == tow_id)
    )
    tow = result.scalar_one_or_none()
    if not tow:
        raise HTTPException(status_code=404, detail="Tow request not found")

    return serialize_tow(tow)


@router.put("/tows/{tow_id}/cancel")
async def admin_cancel_tow(
    tow_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Admin force-cancel a tow request"""
    result = await db.execute(select(TowRequest).where(TowRequest.id == tow_id))
    tow = result.scalar_one_or_none()
    if not tow:
        raise HTTPException(status_code=404, detail="Tow request not found")

    tow.status = TowStatus.CANCELLED
    await db.commit()

    logger.info(f"Admin {admin.email} cancelled tow {tow_id}")
    return {"message": "Tow cancelled"}


# ──────────────────────────────────────────
# FINANCIALS
# ──────────────────────────────────────────

@router.get("/payouts")
async def get_payout_summary(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Get earnings summary per driver"""
    result = await db.execute(
        select(Driver)
        .options(selectinload(Driver.user))
        .where(Driver.approval_status == ApprovalStatus.APPROVED)
        .order_by(Driver.total_tows.desc())
    )
    drivers = result.scalars().all()

    payouts = []
    for d in drivers:
        # Sum completed tow payouts for this driver
        payout_result = await db.execute(
            select(func.sum(TowRequest.driver_payout)).where(
                TowRequest.driver_id == d.id,
                TowRequest.status == TowStatus.COMPLETED
            )
        )
        total_payout = float(payout_result.scalar() or 0)

        revenue_result = await db.execute(
            select(func.sum(TowRequest.final_price)).where(
                TowRequest.driver_id == d.id,
                TowRequest.status == TowStatus.COMPLETED
            )
        )
        total_revenue = float(revenue_result.scalar() or 0)
        commission = total_revenue - total_payout

        payouts.append({
            "driver_id": str(d.id),
            "driver": serialize_user(d.user),
            "total_revenue": total_revenue,
            "total_payout": total_payout,
            "commission_earned": commission,
            "commission_rate": float(d.commission_rate or 15),
            "total_tows": d.total_tows or 0,
            "bank_account_id": d.bank_account_id,
            "rating": float(d.rating or 5),
        })

    return payouts