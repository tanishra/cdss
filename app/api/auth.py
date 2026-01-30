"""
Authentication Routes Module - Following SOLID Principles
Single Responsibility: Authentication endpoints only
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import uuid

from app.core.database import get_db
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    validate_password_strength,
)
from app.core.config import settings
from app.schemas.schemas import DoctorRegister, DoctorLogin, Token, DoctorResponse
from app.models.models import Doctor
from app.utils.correlation import get_correlation_id
from app.core.logging import get_logger, audit_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["authentication"])


class AuthenticationServiceError(Exception):
    """Custom authentication service error."""
    pass


@router.post(
    "/register",
    response_model=DoctorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new doctor",
    description="Register a new doctor account with email and password",
)
async def register(
    doctor_data: DoctorRegister,
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """
    Register a new doctor.
    
    Single Responsibility: User registration only
    """
    correlation_id = get_correlation_id(request)
    
    try:
        # Check if email already exists
        result = await db.execute(
            select(Doctor).where(Doctor.email == doctor_data.email)
        )
        existing_doctor = result.scalar_one_or_none()
        
        if existing_doctor:
            logger.warning(
                "registration_duplicate_email",
                email=doctor_data.email,
                correlation_id=correlation_id,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
        
        # Validate password strength
        try:
            validate_password_strength(doctor_data.password)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )
        
        # Create doctor record
        doctor = Doctor(
            id=str(uuid.uuid4()),
            email=doctor_data.email,
            hashed_password=hash_password(doctor_data.password),
            full_name=doctor_data.full_name,
            specialization=doctor_data.specialization,
            license_number=doctor_data.license_number,
            phone=doctor_data.phone,
        )
        
        db.add(doctor)
        await db.commit()
        await db.refresh(doctor)
        
        # Audit log
        audit_logger.log_authentication(
            doctor_id=doctor.id,
            action="register",
            success=True,
            ip_address=request.client.host if request and request.client else "unknown",
            correlation_id=correlation_id,
        )
        
        logger.info(
            "doctor_registered",
            doctor_id=doctor.id,
            email=doctor.email,
            correlation_id=correlation_id,
        )
        
        return doctor
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "registration_error",
            error=str(e),
            error_type=type(e).__name__,
            correlation_id=correlation_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed",
        )


@router.post(
    "/login",
    response_model=Token,
    summary="Login doctor",
    description="Login with email and password to receive JWT token",
)
async def login(
    credentials: DoctorLogin,
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """
    Login doctor and return JWT token.
    
    Single Responsibility: User login only
    """
    correlation_id = get_correlation_id(request)
    
    try:
        # Get doctor by email
        result = await db.execute(
            select(Doctor).where(Doctor.email == credentials.email)
        )
        doctor = result.scalar_one_or_none()
        
        # Verify credentials
        if not doctor or not verify_password(credentials.password, doctor.hashed_password):
            # Audit failed login
            audit_logger.log_authentication(
                doctor_id=None,
                action="login",
                success=False,
                ip_address=request.client.host if request and request.client else "unknown",
                correlation_id=correlation_id,
            )
            
            logger.warning(
                "login_failed",
                email=credentials.email,
                correlation_id=correlation_id,
            )
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )
        
        # Check if account is active
        if not doctor.is_active:
            logger.warning(
                "login_inactive_account",
                doctor_id=doctor.id,
                correlation_id=correlation_id,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive",
            )
        
        # Create access token
        access_token = create_access_token(data={"sub": doctor.id})
        
        # Update last login
        doctor.last_login = datetime.utcnow()
        await db.commit()
        
        # Audit successful login
        audit_logger.log_authentication(
            doctor_id=doctor.id,
            action="login",
            success=True,
            ip_address=request.client.host if request and request.client else "unknown",
            correlation_id=correlation_id,
        )
        
        logger.info(
            "doctor_logged_in",
            doctor_id=doctor.id,
            correlation_id=correlation_id,
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "login_error",
            error=str(e),
            error_type=type(e).__name__,
            correlation_id=correlation_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed",
        )


@router.get(
    "/me",
    response_model=DoctorResponse,
    summary="Get current doctor",
    description="Get currently authenticated doctor information",
)
async def get_current_doctor_info(
    doctor: Doctor = Depends(get_current_doctor),
):
    """
    Get current authenticated doctor information.
    
    Single Responsibility: Return current user info
    """
    return doctor