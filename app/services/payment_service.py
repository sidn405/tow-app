import stripe
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import settings
from app.models import TowRequest, Driver, User, Transaction, TransactionType, TransactionStatus
from uuid import UUID
from decimal import Decimal
from typing import Dict

stripe.api_key = settings.STRIPE_SECRET_KEY

class PaymentService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_payment_intent(
        self,
        tow_request_id: UUID,
        customer_id: UUID,
        amount: Decimal
    ) -> Dict:
        """
        Create Stripe payment intent for customer
        Authorize payment but don't capture until service is complete
        """
        # Get or create Stripe customer
        stripe_customer = await self._get_or_create_stripe_customer(customer_id)
        
        # Create payment intent (authorized but not captured yet)
        intent = stripe.PaymentIntent.create(
            amount=int(amount * 100),  # Convert to cents
            currency="usd",
            customer=stripe_customer,
            capture_method="manual",  # Authorize only, capture after service
            metadata={
                "tow_request_id": str(tow_request_id),
                "customer_id": str(customer_id)
            },
            description=f"Tow service request {tow_request_id}"
        )
        
        # Update tow request with payment intent
        result = await self.db.execute(
            select(TowRequest).where(TowRequest.id == tow_request_id)
        )
        tow_request = result.scalar_one_or_none()
        
        if tow_request:
            from app.models.tow_request import PaymentStatus
            tow_request.payment_intent_id = intent.id
            tow_request.payment_status = PaymentStatus.AUTHORIZED
            await self.db.commit()
        
        return {
            "client_secret": intent.client_secret,
            "payment_intent_id": intent.id,
            "amount": amount
        }
    
    async def capture_payment(self, tow_request_id: UUID) -> bool:
        """
        Capture payment after tow is completed
        Then initiate driver payout
        """
        # Get tow request
        result = await self.db.execute(
            select(TowRequest).where(TowRequest.id == tow_request_id)
        )
        tow_request = result.scalar_one_or_none()
        
        if not tow_request or not tow_request.payment_intent_id:
            return False
        
        try:
            # Capture the payment
            intent = stripe.PaymentIntent.capture(tow_request.payment_intent_id)
            
            # Update status
            from app.models.tow_request import PaymentStatus
            tow_request.payment_status = PaymentStatus.CAPTURED
            
            # Record transaction
            transaction = Transaction(
                tow_request_id=tow_request_id,
                customer_id=tow_request.customer_id,
                driver_id=tow_request.driver_id,
                amount=tow_request.quoted_price,
                transaction_type=TransactionType.CHARGE,
                stripe_charge_id=intent.id,
                status=TransactionStatus.COMPLETED,
                description=f"Payment for tow {tow_request_id}"
            )
            self.db.add(transaction)
            await self.db.commit()
            
            # Initiate driver payout
            await self.payout_driver(tow_request_id)
            
            return True
            
        except stripe.error.StripeError as e:
            print(f"Stripe error capturing payment: {e}")
            return False
    
    async def payout_driver(self, tow_request_id: UUID) -> bool:
        """
        Transfer funds to driver via Stripe Connect
        This happens after payment is captured from customer
        """
        # Get tow request and driver
        result = await self.db.execute(
            select(TowRequest).where(TowRequest.id == tow_request_id)
        )
        tow_request = result.scalar_one_or_none()
        
        if not tow_request or not tow_request.driver_id:
            return False
        
        driver_result = await self.db.execute(
            select(Driver).where(Driver.id == tow_request.driver_id)
        )
        driver = driver_result.scalar_one_or_none()
        
        if not driver or not driver.bank_account_id:
            return False
        
        try:
            # Create transfer to driver's connected account
            transfer = stripe.Transfer.create(
                amount=int(tow_request.driver_payout * 100),  # in cents
                currency="usd",
                destination=driver.bank_account_id,
                metadata={
                    "tow_request_id": str(tow_request_id),
                    "driver_id": str(driver.id)
                },
                description=f"Payout for tow {tow_request_id}"
            )
            
            # Record transaction
            transaction = Transaction(
                tow_request_id=tow_request_id,
                customer_id=tow_request.customer_id,
                driver_id=tow_request.driver_id,
                amount=tow_request.driver_payout,
                transaction_type=TransactionType.PAYOUT,
                stripe_transfer_id=transfer.id,
                status=TransactionStatus.COMPLETED,
                description=f"Driver payout for tow {tow_request_id}"
            )
            self.db.add(transaction)
            
            # Record platform fee
            platform_transaction = Transaction(
                tow_request_id=tow_request_id,
                customer_id=tow_request.customer_id,
                driver_id=tow_request.driver_id,
                amount=tow_request.platform_fee,
                transaction_type=TransactionType.PLATFORM_FEE,
                status=TransactionStatus.COMPLETED,
                description=f"Platform fee for tow {tow_request_id}"
            )
            self.db.add(platform_transaction)
            
            await self.db.commit()
            return True
            
        except stripe.error.StripeError as e:
            print(f"Stripe error processing payout: {e}")
            return False
    
    async def refund_payment(self, tow_request_id: UUID, reason: str = None) -> bool:
        """
        Refund payment to customer (e.g., if tow is cancelled)
        """
        result = await self.db.execute(
            select(TowRequest).where(TowRequest.id == tow_request_id)
        )
        tow_request = result.scalar_one_or_none()
        
        if not tow_request or not tow_request.payment_intent_id:
            return False
        
        try:
            # Create refund
            refund = stripe.Refund.create(
                payment_intent=tow_request.payment_intent_id,
                reason="requested_by_customer",
                metadata={
                    "tow_request_id": str(tow_request_id),
                    "reason": reason or "Cancelled"
                }
            )
            
            # Update payment status
            from app.models.tow_request import PaymentStatus
            tow_request.payment_status = PaymentStatus.REFUNDED
            
            # Record transaction
            transaction = Transaction(
                tow_request_id=tow_request_id,
                customer_id=tow_request.customer_id,
                amount=tow_request.quoted_price,
                transaction_type=TransactionType.REFUND,
                stripe_refund_id=refund.id,
                status=TransactionStatus.COMPLETED,
                description=f"Refund for cancelled tow {tow_request_id}: {reason}"
            )
            self.db.add(transaction)
            await self.db.commit()
            
            return True
            
        except stripe.error.StripeError as e:
            print(f"Stripe error processing refund: {e}")
            return False
    
    async def setup_driver_connect_account(self, driver_id: UUID, email: str) -> str:
        """
        Create Stripe Connect Express account for driver
        Returns onboarding URL
        """
        # Create Express account
        account = stripe.Account.create(
            type="express",
            email=email,
            capabilities={
                "transfers": {"requested": True}
            },
            business_type="individual",
            metadata={
                "driver_id": str(driver_id)
            }
        )
        
        # Generate onboarding link
        account_link = stripe.AccountLink.create(
            account=account.id,
            refresh_url=f"{settings.WEB_URL}/driver/onboarding",
            return_url=f"{settings.WEB_URL}/driver/dashboard",
            type="account_onboarding"
        )
        
        # Save account ID to driver record
        result = await self.db.execute(
            select(Driver).where(Driver.id == driver_id)
        )
        driver = result.scalar_one_or_none()
        
        if driver:
            driver.bank_account_id = account.id
            await self.db.commit()
        
        return account_link.url
    
    async def _get_or_create_stripe_customer(self, user_id: UUID) -> str:
        """Get existing Stripe customer ID or create new one"""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise ValueError("User not found")
        
        # Check if user already has Stripe customer ID (would need to add field to User model)
        # For now, create new customer each time (in production, cache this)
        customer = stripe.Customer.create(
            email=user.email,
            name=user.full_name,
            phone=user.phone,
            metadata={
                "user_id": str(user_id)
            }
        )
        
        return customer.id
