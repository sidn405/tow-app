from fastapi import APIRouter
from app.config import settings

router = APIRouter(prefix="/api/v1/config", tags=["config"])

@router.get("/stripe-key")
async def get_stripe_key():
    return {"publishable_key": settings.STRIPE_PUBLISHABLE_KEY}