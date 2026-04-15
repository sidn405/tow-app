from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select
from app.config import settings
from app.models import User
from uuid import UUID

pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated="auto",
)

class AuthService:
    @staticmethod
    def hash_password(password: str) -> str:
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against a hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def create_refresh_token(data: dict) -> str:
        """Create JWT refresh token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def decode_token(token: str) -> Optional[dict]:
        """Decode and verify JWT token"""
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]                                 
            )
            
            print(f"🔍 Decode SUCCESS: {payload}")
            return payload
        except jwt.ExpiredSignatureError:
            print(f"🔍 DECODE FAIL: Token expired")
            return None
        except jwt.JWTError as e:
            print(f"🔍 DECODE FAIL: JWT Error: {e}")
            return None
        except Exception as e:
            print(f"🔍 DECODE FAIL: Unexpected error: {type(e).__name__}: {e}")
            return None
    
    @staticmethod
    async def authenticate_user(db: AsyncSession, email: str, password: str) -> Optional[User]:
        """Authenticate user with email and password"""
        result = await db.execute(
            select(User).where(User.email == email, User.is_active == True)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return None
        
        if not AuthService.verify_password(password, user.password_hash):
            return None
        
        return user

    @staticmethod
    async def get_current_user(db: AsyncSession, token: str) -> Optional[User]:
        """Get current user from JWT token"""
        print(f"🔍 AuthService.get_current_user called")
        
        payload = AuthService.decode_token(token)
        print(f"🔍 Payload decoded: {payload is not None}")
        
        if not payload or payload.get("type") != "access":
            print(f"🔍 FAIL: Invalid payload or not access token. Type: {payload.get('type') if payload else 'None'}")
            return None
        
        user_id: str = payload.get("sub")
        print(f"🔍 User ID from token: {user_id}")
        
        if not user_id:
            print(f"🔍 FAIL: No user_id in payload")
            return None
        
        result = await db.execute(
            select(User)
            .options(selectinload(User.driver_profile))  # <-- only change
            .where(User.id == UUID(user_id), User.is_active == True)
        )
        user = result.scalar_one_or_none()
        print(f"🔍 User from DB: {user.email if user else 'None'}")
        
        return user
