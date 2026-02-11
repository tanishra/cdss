"""
Patient and Diagnosis Routes Module - UPDATED with RAG
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.core.database import get_db
from app.api.dependencies import get_current_doctor, check_rate_limit
from app.schemas.schemas import (
    PatientCreate,
    PatientResponse,
    DiagnosisRequest,
    DiagnosisResponseWithEvidence, 
    DifferentialDiagnosisWithEvidence, 
)
from app.services.patient_service import patient_service, PatientServiceError
from app.services.diagnosis_service import diagnosis_service, DiagnosisServiceError
from app.models.models import Doctor
from app.utils.correlation import get_correlation_id
from app.core.logging import get_logger

logger = get_logger(__name__)

# Create separate routers
patient_router = APIRouter(prefix="/patients", tags=["patients"])
diagnosis_router = APIRouter(prefix="/diagnosis", tags=["diagnosis"])


# ============================================================================
# PATIENT ROUTES (Keep existing as is)
# ============================================================================

@patient_router.post("/", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
async def create_patient(
    patient_data: PatientCreate,
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
    _: bool = Depends(check_rate_limit),
    request: Request = None,
):
    """Create new patient record."""
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
        logger.error("patient_creation_failed", error=str(e), correlation_id=correlation_id)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
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


@patient_router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
    request: Request = None,
):
    """Get patient by ID."""
    correlation_id = get_correlation_id(request)
    
    try:
        patient = await patient_service.get_patient(
            db=db,
            patient_id=patient_id,
            doctor_id=current_doctor.id,
            correlation_id=correlation_id,
        )
        
        if not patient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
        
        return patient
        
    except HTTPException:
        raise
    except PatientServiceError as e:
        logger.error("patient_retrieval_failed", error=str(e), correlation_id=correlation_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve patient",
        )

@patient_router.get("/", response_model=List[PatientResponse])
async def list_patients(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
    request: Request = None,
):
    """List all patients for current doctor."""
    correlation_id = get_correlation_id(request)
    
    try:
        patients = await patient_service.list_patients(
            db=db,
            doctor_id=current_doctor.id,
            skip=skip,
            limit=limit,
            correlation_id=correlation_id,
        )
        
        return patients
        
    except PatientServiceError as e:
        logger.error("list_patients_failed", error=str(e), correlation_id=correlation_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list patients",
        )

# ============================================================================
# DIAGNOSIS ROUTES - UPDATED WITH RAG
# ============================================================================

@diagnosis_router.post(
    "/analyze",
    response_model=DiagnosisResponseWithEvidence,
    status_code=status.HTTP_201_CREATED,
    summary="Generate AI-powered diagnosis with medical evidence",
    description="""
    Generate evidence-based differential diagnosis using RAG (Retrieval-Augmented Generation).
    
    **NEW Features:**
    - Medical literature citations from PubMed
    - Clinical practice guidelines
    - Evidence quality scoring
    - Source attribution for each diagnosis
    
    Returns top 5 differential diagnoses with supporting evidence.
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
    Generate evidence-based differential diagnosis.
    
    This endpoint now includes:
    1. Medical literature search (PubMed)
    2. Vector similarity search (past cases)
    3. Clinical guideline integration
    4. Citation tracking
    """
    correlation_id = get_correlation_id(request)
    
    try:
        logger.info(
            "diagnosis_request_received_with_rag",
            patient_id=diagnosis_request.patient_id,
            doctor_id=current_doctor.id,
            chief_complaint=diagnosis_request.chief_complaint,
            symptoms_count=len(diagnosis_request.symptoms),
            has_vitals=diagnosis_request.vital_signs is not None,
            has_labs=diagnosis_request.lab_results is not None,
            rag_enabled=True,
            correlation_id=correlation_id,
        )
        
        # Generate diagnosis with RAG
        # diagnosis = await diagnosis_service.create_diagnosis(
        #     db=db,
        #     request=diagnosis_request,
        #     doctor_id=current_doctor.id,
        #     correlation_id=correlation_id,
        # )
        
        # Transform to response model with evidence
        # differential_diagnoses_with_evidence = []
        
        # for dx in diagnosis.differential_diagnoses:
        #     # Get citations for this diagnosis
        #     citations = [
        #         {
        #             "pubmed_id": c.pubmed_id,
        #             "title": c.title,
        #             "authors": c.authors,
        #             "journal": c.journal,
        #             "publication_year": c.publication_year,
        #             "doi": c.doi,
        #             "citation_text": c.citation_text,
        #             "relevance_score": c.relevance_score,
        #             "evidence_type": c.evidence_type,
        #             "abstract": c.abstract,
        #             "url": c.url,
        #         }
        #         for c in diagnosis.citations
        #         if c.diagnosis_name == dx.get("diagnosis")
        #     ]
            
            # dx_with_evidence = DifferentialDiagnosisWithEvidence(
            #     diagnosis=dx.get("diagnosis"),
            #     confidence=dx.get("confidence"),
            #     icd10_code=dx.get("icd10_code"),
            #     reasoning=dx.get("reasoning"),
            #     supporting_evidence=dx.get("supporting_evidence", []),
            #     contradicting_factors=dx.get("contradicting_factors"),
            #     rank=dx.get("rank"),
            #     citations=citations,
            #     evidence_quality=_calculate_evidence_quality(citations),
            # )
            
            # differential_diagnoses_with_evidence.append(dx_with_evidence)
        
        # response = DiagnosisResponseWithEvidence(
        #     id=diagnosis.id,
        #     patient_id=diagnosis.patient_id,
        #     correlation_id=diagnosis.correlation_id,
        #     chief_complaint=diagnosis.chief_complaint,
        #     symptoms=diagnosis.symptoms,
        #     differential_diagnoses=differential_diagnoses_with_evidence,
        #     clinical_reasoning=diagnosis.clinical_reasoning,
        #     missing_information=diagnosis.missing_information,
        #     red_flags=diagnosis.red_flags,
        #     recommended_tests=diagnosis.recommended_tests,
        #     recommended_treatments=diagnosis.recommended_treatments,
        #     follow_up_instructions=diagnosis.follow_up_instructions,
        #     evidence_used=diagnosis.evidence_used,
        #     guidelines_applied=diagnosis.guidelines_applied,
        #     citation_count=diagnosis.citation_count,
        #     rag_enabled=diagnosis.rag_enabled,
        #     processing_time_ms=diagnosis.processing_time_ms,
        #     confidence_level=_calculate_confidence_level(diagnosis.differential_diagnoses),
        #     created_at=diagnosis.created_at,
        # )
        
        # logger.info(
        #     "diagnosis_generated_successfully_with_evidence",
        #     diagnosis_id=diagnosis.id,
        #     top_diagnosis=diagnosis.differential_diagnoses[0]["diagnosis"] if diagnosis.differential_diagnoses else None,
        #     citation_count=diagnosis.citation_count,
        #     rag_enabled=diagnosis.rag_enabled,
        #     correlation_id=correlation_id,
        # )
        
        # return response
        
    except DiagnosisServiceError as e:
        logger.error("diagnosis_failed", error=str(e), correlation_id=correlation_id)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
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
    """Calculate overall confidence level."""
    if not differential_diagnoses:
        return "Low"
    
    top_confidence = differential_diagnoses[0].get("confidence", 0)
    
    if top_confidence >= 0.75:
        return "High"
    elif top_confidence >= 0.5:
        return "Medium"
    else:
        return "Low"


def _calculate_evidence_quality(citations: list) -> str:
    """Calculate evidence quality based on citations."""
    if not citations:
        return "low"
    
    # Count high-quality sources
    high_quality = sum(
        1 for c in citations
        if c.get("evidence_type") in ["guideline", "meta-analysis", "systematic_review"]
        and c.get("relevance_score", 0) > 0.8
    )
    
    if high_quality >= 2:
        return "high"
    elif high_quality >= 1 or len(citations) >= 3:
        return "moderate"
    else:
        return "low"