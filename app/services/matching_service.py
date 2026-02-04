from typing import List, Dict, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from app.models import Driver, Vehicle, User, TowRequestOffer
from app.config import settings
from uuid import UUID
import asyncio

class MatchingService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def find_available_drivers(
        self,
        pickup_location: Tuple[float, float],  # (lat, lng)
        vehicle_type_id: str,
        requires_flatbed: bool = False,
        max_radius_miles: float = None
    ) -> List[Dict]:
        """
        Find drivers within radius who can handle the request
        Returns drivers sorted by distance, rating, and experience
        """
        if max_radius_miles is None:
            max_radius_miles = settings.MAX_DRIVER_SEARCH_RADIUS_MILES
        
        # Query to find nearby drivers with geographic search
        query = text("""
            SELECT 
                d.id,
                d.user_id,
                u.first_name,
                u.last_name,
                u.phone,
                d.rating,
                d.total_tows,
                v.vehicle_type,
                v.make,
                v.model,
                ST_Distance(
                    d.current_location::geography,
                    ST_MakePoint(:lng, :lat)::geography
                ) / 1609.34 as distance_miles
            FROM drivers d
            JOIN users u ON d.user_id = u.id
            JOIN vehicles v ON v.driver_id = d.id AND v.is_active = TRUE
            WHERE 
                d.is_online = TRUE
                AND d.approval_status = 'approved'
                AND d.current_location IS NOT NULL
                AND :vehicle_type_id = ANY(v.can_tow_types)
                AND ST_DWithin(
                    d.current_location::geography,
                    ST_MakePoint(:lng, :lat)::geography,
                    :max_radius * 1609.34
                )
            ORDER BY 
                distance_miles ASC,
                d.rating DESC,
                d.total_tows DESC
            LIMIT 20
        """)
        
        result = await self.db.execute(
            query,
            {
                "lat": pickup_location[0],
                "lng": pickup_location[1],
                "vehicle_type_id": vehicle_type_id,
                "max_radius": max_radius_miles
            }
        )
        
        drivers = []
        for row in result.fetchall():
            drivers.append({
                "driver_id": row.id,
                "user_id": row.user_id,
                "name": f"{row.first_name} {row.last_name}",
                "phone": row.phone,
                "rating": float(row.rating),
                "total_tows": row.total_tows,
                "vehicle_type": row.vehicle_type,
                "vehicle_info": f"{row.make} {row.model}",
                "distance_miles": float(row.distance_miles)
            })
        
        return drivers
    
    async def send_tow_offers(
        self,
        tow_request_id: UUID,
        drivers: List[Dict],
        batch_size: int = 3
    ) -> None:
        """
        Send tow request offers to drivers in batches
        First batch goes to top 3 drivers simultaneously
        """
        from app.services.notification_service import NotificationService
        
        notification_service = NotificationService(self.db)
        
        # Send to first batch (top 3 drivers)
        primary_batch = drivers[:batch_size]
        
        for driver in primary_batch:
            # Create offer record
            offer = TowRequestOffer(
                tow_request_id=tow_request_id,
                driver_id=driver["driver_id"],
                distance_from_pickup=driver["distance_miles"]
            )
            self.db.add(offer)
            
            # Send push notification
            await notification_service.send_driver_tow_offer(
                driver_id=driver["driver_id"],
                tow_request_id=tow_request_id,
                pickup_address="Pickup location",  # Will be filled from tow_request
                distance_miles=driver["distance_miles"]
            )
        
        await self.db.commit()
        
        # Schedule backup batch after timeout (handled by background worker)
        if len(drivers) > batch_size:
            await self._schedule_backup_offers(
                tow_request_id=tow_request_id,
                remaining_drivers=drivers[batch_size:],
                delay_seconds=settings.DRIVER_ACCEPT_TIMEOUT_SECONDS
            )
    
    async def _schedule_backup_offers(
        self,
        tow_request_id: UUID,
        remaining_drivers: List[Dict],
        delay_seconds: int
    ) -> None:
        """
        Schedule backup driver offers if first batch doesn't accept
        This would typically be handled by Celery/background worker
        """
        # This is a placeholder - actual implementation would use Celery
        # For now, just store in Redis for worker to pick up
        from app.database import redis_client
        import json
        
        await redis_client.setex(
            f"backup_offers:{tow_request_id}",
            delay_seconds,
            json.dumps({
                "tow_request_id": str(tow_request_id),
                "drivers": remaining_drivers,
                "scheduled_at": delay_seconds
            })
        )
    
    async def accept_tow_request(
        self,
        tow_request_id: UUID,
        driver_id: UUID
    ) -> bool:
        """
        Accept a tow request and cancel other pending offers
        Returns True if successful, False if already accepted by another driver
        """
        from app.models import TowRequest, TowStatus
        from app.services.notification_service import NotificationService
        
        # Get tow request
        result = await self.db.execute(
            select(TowRequest).where(TowRequest.id == tow_request_id)
        )
        tow_request = result.scalar_one_or_none()
        
        if not tow_request:
            return False
        
        # Check if already accepted
        if tow_request.status not in [TowStatus.PENDING, TowStatus.SEARCHING]:
            return False
        
        # Update tow request
        tow_request.driver_id = driver_id
        tow_request.status = TowStatus.ACCEPTED
        tow_request.accepted_at = asyncio.get_event_loop().time()
        
        # Update offer status
        result = await self.db.execute(
            select(TowRequestOffer).where(
                TowRequestOffer.tow_request_id == tow_request_id,
                TowRequestOffer.driver_id == driver_id
            )
        )
        offer = result.scalar_one_or_none()
        if offer:
            from app.models.other import OfferResponse
            offer.response = OfferResponse.ACCEPTED
            offer.responded_at = asyncio.get_event_loop().time()
        
        # Cancel other pending offers
        other_offers_result = await self.db.execute(
            select(TowRequestOffer).where(
                TowRequestOffer.tow_request_id == tow_request_id,
                TowRequestOffer.driver_id != driver_id
            )
        )
        for other_offer in other_offers_result.scalars():
            from app.models.other import OfferResponse
            other_offer.response = OfferResponse.EXPIRED
        
        await self.db.commit()
        
        # Notify customer
        notification_service = NotificationService(self.db)
        await notification_service.notify_customer_driver_assigned(
            customer_id=tow_request.customer_id,
            tow_request_id=tow_request_id,
            driver_name="Driver"  # Will be filled with actual driver name
        )
        
        return True
    
    async def reject_tow_request(
        self,
        tow_request_id: UUID,
        driver_id: UUID,
        reason: str = None
    ) -> None:
        """Record driver rejection and potentially notify other drivers"""
        result = await self.db.execute(
            select(TowRequestOffer).where(
                TowRequestOffer.tow_request_id == tow_request_id,
                TowRequestOffer.driver_id == driver_id
            )
        )
        offer = result.scalar_one_or_none()
        
        if offer:
            from app.models.other import OfferResponse
            offer.response = OfferResponse.REJECTED
            offer.responded_at = asyncio.get_event_loop().time()
            offer.rejection_reason = reason
            await self.db.commit()
