"""
Feedback API Routes - NEW
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.dependencies import get_current_doctor
from app.schemas.schemas import (
    DoctorFeedbackCreate,
    DoctorFeedbackResponse,
    FeedbackStats,
)
from app.services.feedback_service import feedback_service, FeedbackServiceError
from app.models.models import Doctor
from app.utils.correlation import get_correlation_id
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post(
    "/",
    response_model=DoctorFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit feedback on diagnosis",
    description="""
    Submit doctor feedback on a diagnosis.
    
    This helps improve the system by:
    - Tracking diagnostic accuracy
    - Identifying common issues
    - Improving future diagnoses
    """,
)
async def create_feedback(
    feedback_data: DoctorFeedbackCreate,
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
    request: Request = None,
):
    """Submit feedback on a diagnosis."""
    correlation_id = get_correlation_id(request)
    
    try:
        feedback = await feedback_service.create_feedback(
            db=db,
            feedback_data=feedback_data,
            doctor_id=current_doctor.id,
            correlation_id=correlation_id,
        )
        
        return feedback
        
    except FeedbackServiceError as e:
        logger.error("feedback_creation_failed", error=str(e), correlation_id=correlation_id)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(
            "feedback_creation_unexpected_error",
            error=str(e),
            correlation_id=correlation_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create feedback",
        )


@router.get(
    "/stats",
    response_model=FeedbackStats,
    summary="Get feedback statistics",
    description="Get aggregated feedback statistics for all diagnoses or specific doctor.",
)
async def get_feedback_statistics(
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
    request: Request = None,
):
    """Get feedback statistics."""
    correlation_id = get_correlation_id(request)
    
    try:
        stats = await feedback_service.get_feedback_stats(
            db=db,
            doctor_id=current_doctor.id,
            correlation_id=correlation_id,
        )
        
        return stats
        
    except Exception as e:
        logger.error("feedback_stats_error", error=str(e), correlation_id=correlation_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get feedback statistics",
        )


@router.get(
    "/diagnosis/{diagnosis_id}",
    response_model=DoctorFeedbackResponse,
    summary="Get feedback for specific diagnosis",
)
async def get_diagnosis_feedback(
    diagnosis_id: str,
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
    request: Request = None,
):
    """Get feedback for a specific diagnosis."""
    correlation_id = get_correlation_id(request)
    
    try:
        feedback = await feedback_service.get_feedback_by_diagnosis(
            db=db,
            diagnosis_id=diagnosis_id,
            doctor_id=current_doctor.id,
            correlation_id=correlation_id,
        )
        
        if not feedback:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Feedback not found for this diagnosis",
            )
        
        return feedback
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_diagnosis_feedback_error", error=str(e), correlation_id=correlation_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get feedback",
        )