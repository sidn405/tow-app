from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import Notification, User, NotificationType
from app.config import settings
from uuid import UUID
from typing import Dict, Optional
import resend
import json

# Initialize Resend
resend.api_key = settings.RESEND_API_KEY

class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def send_notification(
        self,
        user_id: UUID,
        title: str,
        body: str,
        notification_type: NotificationType,
        data: Optional[Dict] = None,
        send_push: bool = True,
        send_email: bool = False,
        send_sms: bool = False
    ) -> Notification:
        """
        Send notification to user via multiple channels
        """
        # Create notification record
        notification = Notification(
            user_id=user_id,
            title=title,
            body=body,
            type=notification_type,
            data=data or {}
        )
        self.db.add(notification)
        await self.db.commit()
        
        # Get user details
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return notification
        
        # Send push notification
        if send_push:
            await self._send_push_notification(user, title, body, data)
        
        # Send email
        if send_email:
            await self._send_email(user.email, title, body)
        
        # Send SMS
        if send_sms:
            await self._send_sms(user.phone, body)
        
        return notification
    
    async def _send_push_notification(
        self,
        user: User,
        title: str,
        body: str,
        data: Optional[Dict] = None
    ):
        """Send push notification via Firebase Cloud Messaging"""
        try:
            # Firebase implementation would go here
            # This is a placeholder for the actual FCM integration
            print(f"Push notification sent to {user.email}: {title}")
            pass
        except Exception as e:
            print(f"Error sending push notification: {e}")
    
    async def _send_email(self, email: str, subject: str, body: str):
        """Send email via Resend"""
        try:
            resend.Emails.send({
                "from": settings.FROM_EMAIL,
                "to": email,
                "subject": subject,
                "html": f"<p>{body}</p>"
            })
        except Exception as e:
            print(f"Error sending email: {e}")
    
    async def _send_sms(self, phone: str, message: str):
        """Send SMS via Twilio"""
        if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
            return
        
        try:
            from twilio.rest import Client
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            
            client.messages.create(
                body=message,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=phone
            )
        except Exception as e:
            print(f"Error sending SMS: {e}")
    
    # Specific notification methods
    async def send_driver_tow_offer(
        self,
        driver_id: UUID,
        tow_request_id: UUID,
        pickup_address: str,
        distance_miles: float
    ):
        """Notify driver of new tow request"""
        result = await self.db.execute(
            select(User).join(User.driver_profile).where(User.driver_profile.has(id=driver_id))
        )
        user = result.scalar_one_or_none()
        
        if user:
            await self.send_notification(
                user_id=user.id,
                title="New Tow Request",
                body=f"New tow request {distance_miles:.1f} miles away from you at {pickup_address}",
                notification_type=NotificationType.TOW_REQUEST,
                data={
                    "tow_request_id": str(tow_request_id),
                    "distance_miles": distance_miles,
                    "pickup_address": pickup_address
                },
                send_push=True,
                send_sms=True  # Send SMS for time-sensitive requests
            )
    
    async def notify_customer_driver_assigned(
        self,
        customer_id: UUID,
        tow_request_id: UUID,
        driver_name: str
    ):
        """Notify customer that a driver has been assigned"""
        await self.send_notification(
            user_id=customer_id,
            title="Driver Assigned",
            body=f"{driver_name} has accepted your tow request and is on the way!",
            notification_type=NotificationType.TOW_UPDATE,
            data={
                "tow_request_id": str(tow_request_id),
                "driver_name": driver_name
            },
            send_push=True,
            send_email=True
        )
    
    async def notify_status_update(
        self,
        user_id: UUID,
        tow_request_id: UUID,
        status: str,
        message: str
    ):
        """Notify user of tow status update"""
        await self.send_notification(
            user_id=user_id,
            title=f"Tow Status: {status}",
            body=message,
            notification_type=NotificationType.TOW_UPDATE,
            data={
                "tow_request_id": str(tow_request_id),
                "status": status
            },
            send_push=True
        )
    
    async def notify_payment_completed(
        self,
        customer_id: UUID,
        tow_request_id: UUID,
        amount: float
    ):
        """Notify customer of successful payment"""
        await self.send_notification(
            user_id=customer_id,
            title="Payment Completed",
            body=f"Your payment of ${amount:.2f} has been processed. Thank you for using our service!",
            notification_type=NotificationType.PAYMENT,
            data={
                "tow_request_id": str(tow_request_id),
                "amount": amount
            },
            send_push=True,
            send_email=True
        )
    
    async def notify_driver_earnings(
        self,
        driver_id: UUID,
        tow_request_id: UUID,
        amount: float
    ):
        """Notify driver of earnings from completed tow"""
        result = await self.db.execute(
            select(User).join(User.driver_profile).where(User.driver_profile.has(id=driver_id))
        )
        user = result.scalar_one_or_none()
        
        if user:
            await self.send_notification(
                user_id=user.id,
                title="Earnings Received",
                body=f"You've earned ${amount:.2f} from your completed tow!",
                notification_type=NotificationType.PAYMENT,
                data={
                    "tow_request_id": str(tow_request_id),
                    "amount": amount
                },
                send_push=True
            )
    
    async def send_welcome_email(self, user_id: UUID):
        """Send welcome email to new user"""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            welcome_message = f"""
            <h2>Welcome to TowTruck Platform, {user.first_name}!</h2>
            <p>Thank you for joining our platform. We're here to provide fast and reliable towing services.</p>
            <p>Download our mobile app to get started and request a tow whenever you need it.</p>
            """
            
            await self._send_email(
                user.email,
                "Welcome to TowTruck Platform",
                welcome_message
            )
    
    async def mark_notification_read(self, notification_id: UUID) -> bool:
        """Mark notification as read"""
        result = await self.db.execute(
            select(Notification).where(Notification.id == notification_id)
        )
        notification = result.scalar_one_or_none()
        
        if notification:
            notification.is_read = True
            await self.db.commit()
            return True
        
        return False
