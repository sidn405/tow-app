from datetime import datetime
from decimal import Decimal
from typing import Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import settings
from app.models import ServiceType, CustomerVehicleType, TowReason

class PricingService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def calculate_tow_price(
        self,
        distance_miles: float,
        service_type_id: str,
        vehicle_type_id: str,
        tow_reason_id: str,
        time_of_day: datetime = None,
        is_surge: bool = False
    ) -> Dict:
        """
        Calculate pricing with fair driver payout
        Customer pays slightly more, driver gets full market rate
        """
        if time_of_day is None:
            time_of_day = datetime.now()
        
        # Get service type
        service_result = await self.db.execute(
            select(ServiceType).where(ServiceType.id == service_type_id)
        )
        service = service_result.scalar_one_or_none()
        
        # Get vehicle type
        vehicle_result = await self.db.execute(
            select(CustomerVehicleType).where(CustomerVehicleType.id == vehicle_type_id)
        )
        vehicle_type = vehicle_result.scalar_one_or_none()
        
        # Get tow reason
        reason_result = await self.db.execute(
            select(TowReason).where(TowReason.id == tow_reason_id)
        )
        tow_reason = reason_result.scalar_one_or_none()
        
        if not service or not vehicle_type or not tow_reason:
            raise ValueError("Invalid service, vehicle type, or tow reason")
        
        # Calculate base price
        base_price = float(service.base_price or settings.DEFAULT_BASE_PRICE)
        per_mile_rate = float(service.per_mile_rate or settings.DEFAULT_PER_MILE_RATE)
        included_miles = service.included_miles or settings.DEFAULT_INCLUDED_MILES
        
        # Add mileage beyond included miles
        extra_miles = max(0, distance_miles - included_miles)
        mileage_fee = extra_miles * per_mile_rate
        
        # Apply vehicle type multiplier
        vehicle_multiplier = float(vehicle_type.price_multiplier)
        vehicle_adjustment = base_price * (vehicle_multiplier - 1)
        
        # Add reason-specific fees
        reason_fee = float(tow_reason.price_adjustment)
        
        # Time-based pricing (night/weekend surcharge)
        time_multiplier = self._get_time_multiplier(time_of_day)
        
        # Surge pricing (high demand periods)
        surge_multiplier = settings.SURGE_MULTIPLIER if is_surge else 1.0
        
        # Calculate subtotal
        subtotal = (base_price + mileage_fee + vehicle_adjustment + reason_fee) * time_multiplier * surge_multiplier
        
        # Industry-standard driver payout (what they'd normally charge)
        driver_base = settings.DRIVER_BASE_RATE
        driver_per_mile = settings.DRIVER_PER_MILE_RATE
        driver_standard_rate = driver_base + (distance_miles * driver_per_mile)
        
        # Platform strategy: Charge customer slightly more, pay driver full market rate
        markup_multiplier = 1 + (settings.CUSTOMER_MARKUP_PERCENTAGE / 100)
        customer_price = max(subtotal, driver_standard_rate * markup_multiplier)
        driver_payout = driver_standard_rate
        platform_fee = customer_price - driver_payout
        
        # Stripe processing fee (2.9% + $0.30)
        stripe_fee = (customer_price * 0.029) + 0.30
        
        net_platform_revenue = platform_fee - stripe_fee
        
        return {
            "customer_price": round(Decimal(str(customer_price)), 2),
            "driver_payout": round(Decimal(str(driver_payout)), 2),
            "platform_fee": round(Decimal(str(platform_fee)), 2),
            "stripe_fee": round(Decimal(str(stripe_fee)), 2),
            "net_revenue": round(Decimal(str(net_platform_revenue)), 2),
            "distance_miles": round(Decimal(str(distance_miles)), 2),
            "estimated_duration_minutes": int(distance_miles * 2.5),  # ~24mph average
            "breakdown": {
                "base": base_price,
                "mileage": mileage_fee,
                "vehicle_adjustment": vehicle_adjustment,
                "reason_fee": reason_fee,
                "time_multiplier": time_multiplier,
                "surge_multiplier": surge_multiplier,
                "driver_standard_rate": driver_standard_rate,
                "customer_markup_percentage": settings.CUSTOMER_MARKUP_PERCENTAGE
            }
        }
    
    def _get_time_multiplier(self, dt: datetime) -> float:
        """Calculate time-based pricing multiplier for night and weekend hours"""
        hour = dt.hour
        is_weekend = dt.weekday() >= 5
        
        # Night hours (10 PM - 6 AM): 1.25x
        if hour >= 22 or hour < 6:
            return settings.NIGHT_SURCHARGE_MULTIPLIER
        # Weekend: 1.15x
        elif is_weekend:
            return settings.WEEKEND_SURCHARGE_MULTIPLIER
        else:
            return 1.0
    
    async def apply_promo_code(self, base_price: Decimal, promo_code: str) -> Dict:
        """Apply promo code discount"""
        from app.models import PromoCode
        
        result = await self.db.execute(
            select(PromoCode).where(
                PromoCode.code == promo_code.upper(),
                PromoCode.is_active == True
            )
        )
        promo = result.scalar_one_or_none()
        
        if not promo:
            raise ValueError("Invalid or inactive promo code")
        
        # Check validity dates
        now = datetime.now()
        if promo.valid_from and now < promo.valid_from:
            raise ValueError("Promo code not yet valid")
        if promo.valid_until and now > promo.valid_until:
            raise ValueError("Promo code has expired")
        
        # Check max uses
        if promo.max_uses and promo.used_count >= promo.max_uses:
            raise ValueError("Promo code usage limit reached")
        
        # Calculate discount
        if promo.discount_type == "percentage":
            discount = base_price * (promo.discount_value / 100)
        else:  # fixed
            discount = promo.discount_value
        
        final_price = max(Decimal("0"), base_price - discount)
        
        return {
            "original_price": base_price,
            "discount": discount,
            "final_price": final_price,
            "promo_code": promo.code
        }
