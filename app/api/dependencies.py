"""
API Dependencies Module - Following SOLID Principles
Dependency Inversion: Inject dependencies rather than create them
"""
from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import decode_access_token
from app.core.cache import rate_limiter
from app.models.models import Doctor
from app.utils.correlation import get_correlation_id
from app.core.logging import get_logger

logger = get_logger(__name__)
security = HTTPBearer()


class AuthenticationError(Exception):
    """Custom authentication error."""
    pass


class RateLimitError(Exception):
    """Custom rate limit error."""
    pass


async def get_current_doctor(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
) -> Doctor:
    """
    Get current authenticated doctor.
    
    Dependency Inversion: Returns abstraction (Doctor model)
    Single Responsibility: Authentication only
    """
    try:
        # Decode JWT token
        token = credentials.credentials
        payload = decode_access_token(token)
        doctor_id: str = payload.get("sub")
        
        # Fetch doctor from database
        result = await db.execute(
            select(Doctor).where(
                Doctor.id == doctor_id,
                Doctor.is_active == True
            )
        )
        doctor = result.scalar_one_or_none()
        
        if doctor is None:
            logger.warning(
                "doctor_not_found",
                doctor_id=doctor_id,
                correlation_id=get_correlation_id(request) if request else None,
            )
            raise AuthenticationError("Doctor not found or inactive")
        
        logger.debug(
            "doctor_authenticated",
            doctor_id=doctor.id,
            correlation_id=get_correlation_id(request) if request else None,
        )
        
        return doctor
        
    except AuthenticationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("authentication_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def check_rate_limit(
    request: Request,
    doctor: Doctor = Depends(get_current_doctor),
) -> bool:
    """
    Check rate limiting for authenticated user.
    
    Single Responsibility: Rate limit checking only
    """
    try:
        identifier = f"doctor:{doctor.id}"
        correlation_id = get_correlation_id(request)
        
        is_allowed = await rate_limiter.is_allowed(identifier)
        
        if not is_allowed:
            logger.warning(
                "rate_limit_exceeded",
                doctor_id=doctor.id,
                correlation_id=correlation_id,
            )
            raise RateLimitError("Rate limit exceeded")
        
        return True
        
    except RateLimitError:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later.",
        )
    except Exception as e:
        logger.error("rate_limit_check_error", error=str(e))
        # Fail open - allow request if rate limiting fails
        return True


async def get_optional_doctor(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Optional[Doctor]:
    """
    Get current doctor if authenticated, None otherwise.
    
    Used for optional authentication endpoints.
    """
    if not credentials:
        return None
    
    try:
        return await get_current_doctor(credentials, db)
    except HTTPException:
        return None