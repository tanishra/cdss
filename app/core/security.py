"""
Security Module
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)

def hash_password(password: str) -> str:
    """Hash a password."""
    try:
        # Encode to bytes and truncate to 72 bytes for bcrypt
        password_bytes = password.encode('utf-8')[:72]
        password = password_bytes.decode('utf-8')
        return pwd_context.hash(password)
    except Exception as e:
        logger.error("password_hash_error", error=str(e))
        raise


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password."""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error("password_verify_error", error=str(e))
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token."""
    try:
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire, "iat": datetime.utcnow()})
        
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        
        return encoded_jwt
    except Exception as e:
        logger.error("token_creation_error", error=str(e))
        raise


def decode_access_token(token: str) -> dict:
    """Decode JWT token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
            )
        
        return payload
    except JWTError as e:
        logger.warning("token_decode_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


def validate_password_strength(password: str) -> bool:
    """Validate password strength."""
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")
    if not any(c.isupper() for c in password):
        raise ValueError("Password must contain uppercase letter")
    if not any(c.islower() for c in password):
        raise ValueError("Password must contain lowercase letter")
    if not any(c.isdigit() for c in password):
        raise ValueError("Password must contain digit")
    return True