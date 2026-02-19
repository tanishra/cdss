"""
Patient Authentication API Routes
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta

from app.core.database import get_db
from app.models.models import PatientUser, Patient
from app.schemas.schemas import PatientUserCreate, PatientUserLogin, PatientUserResponse
from app.core.security import get_password_hash, verify_password, create_access_token
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


def get_correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", "")


@router.post("/register", response_model=PatientUserResponse)
async def register_patient_user(
    user: PatientUserCreate,
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """Register patient user account."""
    correlation_id = get_correlation_id(request)
    
    try:
        # Check if email exists
        result = await db.execute(
            select(PatientUser).where(PatientUser.email == user.email)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Check if patient exists
        patient_result = await db.execute(
            select(Patient).where(Patient.id == user.patient_id)
        )
        patient = patient_result.scalar_one_or_none()
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found"
            )
        
        # Check if patient already has account
        existing_account = await db.execute(
            select(PatientUser).where(PatientUser.patient_id == user.patient_id)
        )
        if existing_account.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Patient already has an account"
            )
        
        # Create patient user
        hashed_password = get_password_hash(user.password)
        
        new_user = PatientUser(
            email=user.email,
            hashed_password=hashed_password,
            patient_id=user.patient_id,
            is_active=True,
        )
        
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        
        logger.info(
            "patient_user_registered",
            user_id=new_user.id,
            patient_id=user.patient_id,
            correlation_id=correlation_id,
        )
        
        return new_user
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("patient_registration_error", error=str(e), correlation_id=correlation_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post("/login")
async def login_patient_user(
    credentials: PatientUserLogin,
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """Patient user login."""
    correlation_id = get_correlation_id(request)
    
    try:
        result = await db.execute(
            select(PatientUser).where(PatientUser.email == credentials.email)
        )
        user = result.scalar_one_or_none()
        
        if not user or not verify_password(credentials.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive"
            )
        
        # Update last login
        user.last_login = datetime.utcnow()
        await db.commit()
        
        # Create token
        access_token = create_access_token(
            data={"sub": user.email, "user_id": user.id, "user_type": "patient"}
        )
        
        logger.info(
            "patient_user_login",
            user_id=user.id,
            patient_id=user.patient_id,
            correlation_id=correlation_id,
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "patient_id": user.patient_id,
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("patient_login_error", error=str(e), correlation_id=correlation_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


# Dependency to get current patient user
async def get_current_patient_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> PatientUser:
    """Get current authenticated patient user."""
    from app.core.security import decode_access_token
    
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    token = auth_header.split(" ")[1]
    payload = decode_access_token(token)
    
    if not payload or payload.get("user_type") != "patient":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    
    user_id = payload.get("user_id")
    result = await db.execute(
        select(PatientUser).where(PatientUser.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    return user