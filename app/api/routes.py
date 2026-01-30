"""
Patient and Diagnosis Routes Module - Following SOLID Principles
Interface Segregation: Separate routes for different resources
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.dependencies import get_current_doctor, check_rate_limit
from app.schemas.schemas import (
    PatientCreate,
    PatientResponse,
    DiagnosisRequest,
    DiagnosisResponse,
)
from app.services.patient_service import patient_service, PatientServiceError
from app.services.diagnosis_service import diagnosis_service, DiagnosisServiceError
from app.models.models import Doctor
from app.utils.correlation import get_correlation_id
from app.core.logging import get_logger

logger = get_logger(__name__)

# Create separate routers - Interface Segregation Principle
patient_router = APIRouter(prefix="/patients", tags=["patients"])
diagnosis_router = APIRouter(prefix="/diagnosis", tags=["diagnosis"])


# ============================================================================
# PATIENT ROUTES - Single Responsibility Principle
# ============================================================================

@patient_router.post(
    "/",
    response_model=PatientResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create patient",
    description="Create a new patient record with complete medical history",
)
async def create_patient(
    patient_data: PatientCreate,
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
    _: bool = Depends(check_rate_limit),
    request: Request = None,
):
    """
    Create new patient record.
    
    Single Responsibility: Patient creation endpoint
    """
    correlation_id = get_correlation_id(request)
    
    try:
        logger.info(
            "patient_creation_request",
            doctor_id=current_doctor.id,
            mrn=patient_data.mrn,
            correlation_id=correlation_id,
        )
        
        patient = await patient_service.create_patient(
            db=db,
            patient_data=patient_data,
            doctor_id=current_doctor.id,
            correlation_id=correlation_id,
        )
        
        return patient
        
    except PatientServiceError as e:
        logger.error(
            "patient_creation_failed",
            error=str(e),
            correlation_id=correlation_id,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            "patient_creation_unexpected_error",
            error=str(e),
            error_type=type(e).__name__,
            correlation_id=correlation_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create patient",
        )


@patient_router.get(
    "/{patient_id}",
    response_model=PatientResponse,
    summary="Get patient",
    description="Get patient details by ID",
)
async def get_patient(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
    request: Request = None,
):
    """
    Get patient by ID.
    
    Single Responsibility: Patient retrieval endpoint
    """
    correlation_id = get_correlation_id(request)
    
    try:
        patient = await patient_service.get_patient(
            db=db,
            patient_id=patient_id,
            doctor_id=current_doctor.id,
            correlation_id=correlation_id,
        )
        
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found",
            )
        
        return patient
        
    except HTTPException:
        raise
    except PatientServiceError as e:
        logger.error(
            "patient_retrieval_failed",
            error=str(e),
            correlation_id=correlation_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve patient",
        )
    except Exception as e:
        logger.error(
            "patient_retrieval_unexpected_error",
            error=str(e),
            error_type=type(e).__name__,
            correlation_id=correlation_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve patient",
        )


# ============================================================================
# DIAGNOSIS ROUTES - Single Responsibility Principle
# ============================================================================

@diagnosis_router.post(
    "/analyze",
    response_model=DiagnosisResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate diagnosis",
    description="""
    Analyze patient symptoms and generate AI-powered differential diagnosis.
    
    Returns top 5 most likely diagnoses with:
    - Confidence scores
    - Clinical reasoning
    - Recommended tests
    - Treatment suggestions
    - Follow-up instructions
    """,
)
async def analyze_symptoms(
    diagnosis_request: DiagnosisRequest,
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
    _: bool = Depends(check_rate_limit),
    request: Request = None,
):
    """
    Generate differential diagnosis using AI.
    
    Single Responsibility: Diagnosis generation endpoint
    
    Process:
    1. Validate patient exists and belongs to doctor
    2. Gather patient history and demographics
    3. Use Claude AI to generate top 5 differential diagnoses
    4. Provide clinical reasoning and recommendations
    5. Log audit trail
    """
    correlation_id = get_correlation_id(request)
    
    try:
        logger.info(
            "diagnosis_request_received",
            patient_id=diagnosis_request.patient_id,
            doctor_id=current_doctor.id,
            chief_complaint=diagnosis_request.chief_complaint,
            symptoms_count=len(diagnosis_request.symptoms),
            has_vitals=diagnosis_request.vital_signs is not None,
            has_labs=diagnosis_request.lab_results is not None,
            correlation_id=correlation_id,
        )
        
        # Generate diagnosis
        diagnosis = await diagnosis_service.create_diagnosis(
            db=db,
            request=diagnosis_request,
            doctor_id=current_doctor.id,
            correlation_id=correlation_id,
        )
        
        # Transform to response model
        response = DiagnosisResponse(
            id=diagnosis.id,
            patient_id=diagnosis.patient_id,
            correlation_id=diagnosis.correlation_id,
            chief_complaint=diagnosis.chief_complaint,
            symptoms=diagnosis.symptoms,
            differential_diagnoses=diagnosis.differential_diagnoses,
            clinical_reasoning=diagnosis.clinical_reasoning,
            missing_information=diagnosis.missing_information,
            red_flags=diagnosis.red_flags,
            recommended_tests=diagnosis.recommended_tests,
            recommended_treatments=diagnosis.recommended_treatments,
            follow_up_instructions=diagnosis.follow_up_instructions,
            processing_time_ms=diagnosis.processing_time_ms,
            confidence_level=_calculate_confidence_level(diagnosis.differential_diagnoses),
            created_at=diagnosis.created_at,
        )
        
        logger.info(
            "diagnosis_generated_successfully",
            diagnosis_id=diagnosis.id,
            top_diagnosis=diagnosis.differential_diagnoses[0]["diagnosis"] if diagnosis.differential_diagnoses else None,
            confidence=diagnosis.differential_diagnoses[0]["confidence"] if diagnosis.differential_diagnoses else None,
            correlation_id=correlation_id,
        )
        
        return response
        
    except DiagnosisServiceError as e:
        logger.error(
            "diagnosis_failed",
            error=str(e),
            correlation_id=correlation_id,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            "diagnosis_unexpected_error",
            error=str(e),
            error_type=type(e).__name__,
            correlation_id=correlation_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate diagnosis",
        )


def _calculate_confidence_level(differential_diagnoses: list) -> str:
    """
    Calculate overall confidence level from diagnoses.
    
    Single Responsibility: Confidence calculation helper
    """
    if not differential_diagnoses:
        return "Low"
    
    top_confidence = differential_diagnoses[0].get("confidence", 0)
    
    if top_confidence >= 0.75:
        return "High"
    elif top_confidence >= 0.5:
        return "Medium"
    else:
        return "Low"