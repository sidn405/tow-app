from resend import Resend
from app.config import settings
from jinja2 import Template
import os

resend = Resend(api_key=settings.RESEND_API_KEY)

class EmailService:
    
    @staticmethod
    async def send_receipt_email(
        customer_email: str,
        customer_name: str,
        tow_data: dict
    ):
        """Send receipt email after tow completion"""
        
        # Load template
        template_path = os.path.join(os.path.dirname(__file__), '../templates/receipt_email.html')
        with open(template_path, 'r') as f:
            template = Template(f.read())
        
        # Render template with data
        html_content = template.render(
            customer_name=customer_name,
            receipt_number=str(tow_data['id'])[:8].upper(),
            completion_date=tow_data['completed_at'].strftime('%B %d, %Y at %I:%M %p'),
            vehicle=f"{tow_data['vehicle_year']} {tow_data['vehicle_make']} {tow_data['vehicle_model']}",
            pickup_address=tow_data['pickup_address'],
            dropoff_address=tow_data['dropoff_address'],
            distance_miles=tow_data['distance_miles'],
            driver_name=tow_data.get('driver_name', 'Your Driver'),
            base_price=f"{float(tow_data['quoted_price'] - tow_data['platform_fee'] - tow_data['stripe_fee']):.2f}",
            platform_fee=f"{float(tow_data['platform_fee']):.2f}",
            stripe_fee=f"{float(tow_data['stripe_fee']):.2f}",
            total_price=f"{float(tow_data['quoted_price']):.2f}",
            card_last4=tow_data.get('card_last4', '****'),
            receipt_url=f"{settings.WEB_URL}/receipt.html?id={tow_data['id']}"
        )
        
        try:
            # Send email
            response = resend.emails.send({
                "from": "TowNow <receipts@townow.com>",  # Change to your verified domain
                "to": customer_email,
                "subject": f"Your TowNow Receipt - {tow_data['vehicle_make']} {tow_data['vehicle_model']}",
                "html": html_content
            })
            
            return True
        except Exception as e:
            print(f"Error sending receipt email: {e}")
            return False