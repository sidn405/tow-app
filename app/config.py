from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Application
    APP_NAME: str = "TowTruck Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    
    # Database
    DATABASE_URL: str
    
    # Redis
    REDIS_URL: str
    
    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Stripe
    STRIPE_SECRET_KEY: str
    STRIPE_PUBLISHABLE_KEY: str
    STRIPE_WEBHOOK_SECRET: str
    
    # Resend Email
    RESEND_API_KEY: str
    FROM_EMAIL: str = "noreply@towtruck.com"
    
    # OpenAI
    OPENAI_API_KEY: str
    
    # Firebase (for push notifications)
    FIREBASE_CREDENTIALS: Optional[str] = None
    
    # Twilio (for SMS)
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_PHONE_NUMBER: Optional[str] = None
    
    # AWS S3
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_S3_BUCKET: Optional[str] = None
    AWS_REGION: str = "us-east-1"
    
    # Application URLs
    WEB_URL: str = "https://towtruck.com"
    API_URL: str = "https://api.towtruck.com"
    
    # Business Logic
    PLATFORM_FEE_PERCENTAGE: float = 15.0
    MAX_DRIVER_SEARCH_RADIUS_MILES: float = 15.0
    DRIVER_ACCEPT_TIMEOUT_SECONDS: int = 30
    LOCATION_UPDATE_INTERVAL_SECONDS: int = 5
    
    # Pricing defaults
    DEFAULT_BASE_PRICE: float = 75.0
    DEFAULT_PER_MILE_RATE: float = 3.5
    DEFAULT_INCLUDED_MILES: int = 5
    NIGHT_SURCHARGE_MULTIPLIER: float = 1.25
    WEEKEND_SURCHARGE_MULTIPLIER: float = 1.15
    SURGE_MULTIPLIER: float = 1.5
    
    # Driver market rates
    DRIVER_BASE_RATE: float = 100.0
    DRIVER_PER_MILE_RATE: float = 4.0
    CUSTOMER_MARKUP_PERCENTAGE: float = 15.0
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
