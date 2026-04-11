from fastapi import APIRouter
from app.config import settings

router = APIRouter(prefix="/api/v1/config", tags=["config"])

@router.get("/stripe-key")
async def get_stripe_key():
    """Return Stripe publishable key for frontend"""
    return {
        "publishable_key": settings.STRIPE_PUBLISHABLE_KEY
    }

@router.get("/mapbox-token")
async def get_mapbox_token():
    """Return Mapbox public token"""
    return {
        "token": settings.MAPBOX_PUBLIC_TOKEN
    }