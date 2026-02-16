"""
Treatment API Routes
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.core.database import get_db
from app.api.dependencies import get_current_doctor
from app.models.models import Doctor
from app.schemas.schemas import (
    TreatmentCreate,
    TreatmentUpdate,
    TreatmentResponse,
    PrescriptionCreate,
    PrescriptionResponse,
)
from app.services.treatment_service import treatment_service, TreatmentServiceError
from app.core.logging import get_logger


logger = get_logger(__name__)
router = APIRouter(prefix="/treatment", tags=["treatments"])

def get_correlation_id(request: Request) -> str:
    """Get correlation ID from request state."""
    return getattr(request.state, "correlation_id", "")


@router.post("/", response_model=TreatmentResponse, status_code=status.HTTP_201_CREATED)
async def create_treatment(
    treatment: TreatmentCreate,
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
    request: Request = None,
):
    """Create new treatment record."""
    correlation_id = get_correlation_id(request)
    
    try:
        # Get patient_id from diagnosis
        from app.models.models import Diagnosis
        from sqlalchemy import select
        
        result = await db.execute(
            select(Diagnosis).where(Diagnosis.id == treatment.diagnosis_id)
        )
        diagnosis = result.scalar_one_or_none()
        
        if not diagnosis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Diagnosis not found"
            )
        
        treatment_data = treatment.dict()
        created_treatment = await treatment_service.create_treatment(
            db=db,
            treatment_data=treatment_data,
            patient_id=diagnosis.patient_id,
            doctor_id=current_doctor.id,
            correlation_id=correlation_id,
        )
        
        return created_treatment
        
    except TreatmentServiceError as e:
        logger.error("create_treatment_failed", error=str(e), correlation_id=correlation_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.patch("/{treatment_id}", response_model=TreatmentResponse)
async def update_treatment(
    treatment_id: str,
    treatment_update: TreatmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
    request: Request = None,
):
    """Update treatment outcome."""
    correlation_id = get_correlation_id(request)
    
    try:
        update_data = treatment_update.dict(exclude_unset=True)
        
        updated_treatment = await treatment_service.update_treatment(
            db=db,
            treatment_id=treatment_id,
            update_data=update_data,
            doctor_id=current_doctor.id,
            correlation_id=correlation_id,
        )
        
        return updated_treatment
        
    except TreatmentServiceError as e:
        logger.error("update_treatment_failed", error=str(e), correlation_id=correlation_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get("/patient/{patient_id}", response_model=List[TreatmentResponse])
async def get_patient_treatments(
    patient_id: str,
    active_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
    request: Request = None,
):
    """Get all treatments for a patient."""
    correlation_id = get_correlation_id(request)
    
    try:
        treatments = await treatment_service.get_patient_treatments(
            db=db,
            patient_id=patient_id,
            doctor_id=current_doctor.id,
            active_only=active_only,
            correlation_id=correlation_id,
        )
        
        return treatments
        
    except TreatmentServiceError as e:
        logger.error("get_treatments_failed", error=str(e), correlation_id=correlation_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/prescriptions", response_model=PrescriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_prescription(
    prescription: PrescriptionCreate,
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
    request: Request = None,
):
    """Create prescription."""
    correlation_id = get_correlation_id(request)
    
    try:
        prescription_data = prescription.dict()
        
        created_prescription = await treatment_service.create_prescription(
            db=db,
            prescription_data=prescription_data,
            doctor_id=current_doctor.id,
            correlation_id=correlation_id,
        )
        
        return created_prescription
        
    except TreatmentServiceError as e:
        logger.error("create_prescription_failed", error=str(e), correlation_id=correlation_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/analytics", response_model=dict)
async def get_treatment_analytics(
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
    request: Request = None,
):
    """Get treatment effectiveness analytics."""
    correlation_id = get_correlation_id(request)
    
    try:
        analytics = await treatment_service.get_treatment_analytics(
            db=db,
            doctor_id=current_doctor.id,
            correlation_id=correlation_id,
        )
        
        return analytics
        
    except TreatmentServiceError as e:
        logger.error("analytics_failed", error=str(e), correlation_id=correlation_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )