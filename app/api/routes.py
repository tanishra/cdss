"""
Patient and Diagnosis Routes Module - UPDATED with RAG
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi import UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, String
from pydantic import EmailStr
from typing import List, Dict, Any, Optional
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
from app.services.pdf_service import pdf_service
from app.models.models import Doctor, Diagnosis, Patient, DoctorFeedback
from app.utils.correlation import get_correlation_id
from app.core.logging import get_logger
import io
from datetime import datetime

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
        diagnosis = await diagnosis_service.create_diagnosis(
            db=db,
            request=diagnosis_request,
            doctor_id=current_doctor.id,
            correlation_id=correlation_id,
        )
        
        # Transform to response model with evidence
        differential_diagnoses_with_evidence = []
        
        for dx in diagnosis.differential_diagnoses:
            # Get citations for this diagnosis
            citations_list = []
            if diagnosis.evidence_used:
                for evidence in diagnosis.evidence_used[:3]:  # Top 3
                    citations_list.append({
                        "pubmed_id": evidence.get("pubmed_id"),
                        "title": evidence.get("title", ""),
                        "authors": evidence.get("authors", ""),
                        "journal": evidence.get("journal", ""),
                        "publication_year": evidence.get("publication_year"),
                        "doi": evidence.get("doi"),
                        "citation_text": evidence.get("citation_text", ""),
                        "relevance_score": evidence.get("relevance_score", 0.9),
                        "evidence_type": evidence.get("evidence_type", "research"),
                        "abstract": evidence.get("abstract", ""),
                        "url": evidence.get("url", ""),
                    })
            
            dx_with_evidence = DifferentialDiagnosisWithEvidence(
                diagnosis=dx.get("diagnosis"),
                confidence=dx.get("confidence"),
                icd10_code=dx.get("icd10_code"),
                reasoning=dx.get("reasoning"),
                supporting_evidence=dx.get("supporting_evidence", []),
                contradicting_factors=dx.get("contradicting_factors"),
                rank=dx.get("rank"),
                citations=citations_list,
                evidence_quality=_calculate_evidence_quality(citations_list),
            )
            
            differential_diagnoses_with_evidence.append(dx_with_evidence)
        
        response = DiagnosisResponseWithEvidence(
            id=diagnosis.id,
            patient_id=diagnosis.patient_id,
            correlation_id=diagnosis.correlation_id,
            chief_complaint=diagnosis.chief_complaint,
            symptoms=diagnosis.symptoms,
            differential_diagnoses=differential_diagnoses_with_evidence,
            clinical_reasoning=diagnosis.clinical_reasoning,
            missing_information=diagnosis.missing_information,
            red_flags=diagnosis.red_flags,
            recommended_tests=diagnosis.recommended_tests,
            recommended_treatments=diagnosis.recommended_treatments,
            follow_up_instructions=diagnosis.follow_up_instructions,
            evidence_used=diagnosis.evidence_used,
            guidelines_applied=diagnosis.guidelines_applied,
            citation_count=diagnosis.citation_count,
            rag_enabled=diagnosis.rag_enabled,
            processing_time_ms=diagnosis.processing_time_ms,
            confidence_level=_calculate_confidence_level(diagnosis.differential_diagnoses),
            created_at=diagnosis.created_at,
        )
        
        logger.info(
            "diagnosis_generated_successfully_with_evidence",
            diagnosis_id=diagnosis.id,
            top_diagnosis=diagnosis.differential_diagnoses[0]["diagnosis"] if diagnosis.differential_diagnoses else None,
            citation_count=diagnosis.citation_count,
            rag_enabled=diagnosis.rag_enabled,
            correlation_id=correlation_id,
        )
        
        return response
        
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


@diagnosis_router.get("/search", response_model=List[DiagnosisResponseWithEvidence])
async def search_diagnoses(
    # Search params
    query: Optional[str] = None,
    patient_id: Optional[str] = None,
    disease: Optional[str] = None,
    symptom: Optional[str] = None,
    
    # Filter params
    confidence_level: Optional[str] = None,  # High, Medium, Low
    min_citations: Optional[int] = None,
    has_feedback: Optional[bool] = None,
    feedback_rating_min: Optional[int] = None,  # 1-5
    
    # Date range
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    
    # Pagination
    skip: int = 0,
    limit: int = 50,
    
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
    request: Request = None,
):
    """Advanced search and filter diagnoses."""
    correlation_id = get_correlation_id(request)
    
    try:
        from sqlalchemy import or_, and_, func
        from datetime import datetime
        
        # Base query
        query_builder = select(Diagnosis).where(
            and_(
                Diagnosis.doctor_id == current_doctor.id,
                Diagnosis.is_active == True
            )
        )
        
        # Text search (chief complaint, symptoms, diagnoses)
        if query:
            query_lower = f"%{query.lower()}%"
            query_builder = query_builder.where(
                or_(
                    func.lower(Diagnosis.chief_complaint).like(query_lower),
                    func.cast(Diagnosis.symptoms, String).like(query_lower),
                    func.cast(Diagnosis.differential_diagnoses, String).like(query_lower),
                )
            )
        
        # Patient filter
        if patient_id:
            query_builder = query_builder.where(Diagnosis.patient_id == patient_id)
        
        # Disease filter (search in differential_diagnoses)
        if disease:
            disease_lower = f"%{disease.lower()}%"
            query_builder = query_builder.where(
                func.cast(Diagnosis.differential_diagnoses, String).like(disease_lower)
            )
        
        # Symptom filter
        if symptom:
            symptom_lower = f"%{symptom.lower()}%"
            query_builder = query_builder.where(
                func.cast(Diagnosis.symptoms, String).like(symptom_lower)
            )
        
        # Confidence level filter
        if confidence_level:
            # Calculate confidence level from differential_diagnoses
            if confidence_level == "High":
                query_builder = query_builder.where(
                    func.cast(Diagnosis.differential_diagnoses, String).like('%"confidence": 0.7%')
                )
            elif confidence_level == "Medium":
                query_builder = query_builder.where(
                    and_(
                        func.cast(Diagnosis.differential_diagnoses, String).like('%"confidence": 0.5%'),
                        ~func.cast(Diagnosis.differential_diagnoses, String).like('%"confidence": 0.7%')
                    )
                )
            elif confidence_level == "Low":
                query_builder = query_builder.where(
                    ~func.cast(Diagnosis.differential_diagnoses, String).like('%"confidence": 0.5%')
                )
        
        # Citations filter
        if min_citations is not None:
            query_builder = query_builder.where(Diagnosis.citation_count >= min_citations)
        
        # Feedback filter
        if has_feedback:
            query_builder = query_builder.join(DoctorFeedback, Diagnosis.id == DoctorFeedback.diagnosis_id)
            
            if feedback_rating_min is not None:
                query_builder = query_builder.where(
                    DoctorFeedback.overall_satisfaction >= feedback_rating_min
                )
        
        # Date range
        if date_from:
            date_from_obj = datetime.fromisoformat(date_from)
            query_builder = query_builder.where(Diagnosis.created_at >= date_from_obj)
        
        if date_to:
            date_to_obj = datetime.fromisoformat(date_to)
            query_builder = query_builder.where(Diagnosis.created_at <= date_to_obj)
        
        # Order by most recent
        query_builder = query_builder.order_by(Diagnosis.created_at.desc())
        
        # Pagination
        query_builder = query_builder.offset(skip).limit(limit)
        
        # Execute
        result = await db.execute(query_builder)
        diagnoses = result.scalars().all()
        
        # Build response
        response_list = []
        for diagnosis in diagnoses:
            differential_diagnoses_with_evidence = []
            
            for dx in diagnosis.differential_diagnoses:
                citations_list = []
                if diagnosis.evidence_used:
                    for evidence in diagnosis.evidence_used[:3]:
                        citations_list.append({
                            "pubmed_id": evidence.get("pubmed_id"),
                            "title": evidence.get("title", ""),
                            "authors": evidence.get("authors", ""),
                            "journal": evidence.get("journal", ""),
                            "publication_year": evidence.get("publication_year"),
                            "doi": evidence.get("doi"),
                            "citation_text": evidence.get("citation_text", ""),
                            "relevance_score": evidence.get("relevance_score", 0.9),
                            "evidence_type": evidence.get("evidence_type", "research"),
                            "abstract": evidence.get("abstract", ""),
                            "url": evidence.get("url", ""),
                        })
                
                dx_with_evidence = DifferentialDiagnosisWithEvidence(
                    diagnosis=dx.get("diagnosis"),
                    confidence=dx.get("confidence"),
                    icd10_code=dx.get("icd10_code"),
                    reasoning=dx.get("reasoning"),
                    supporting_evidence=dx.get("supporting_evidence", []),
                    contradicting_factors=dx.get("contradicting_factors"),
                    rank=dx.get("rank"),
                    citations=citations_list,
                    evidence_quality=_calculate_evidence_quality(citations_list),
                )
                differential_diagnoses_with_evidence.append(dx_with_evidence)
            
            response = DiagnosisResponseWithEvidence(
                id=diagnosis.id,
                patient_id=diagnosis.patient_id,
                correlation_id=diagnosis.correlation_id,
                chief_complaint=diagnosis.chief_complaint,
                symptoms=diagnosis.symptoms,
                differential_diagnoses=differential_diagnoses_with_evidence,
                clinical_reasoning=diagnosis.clinical_reasoning,
                missing_information=diagnosis.missing_information,
                red_flags=diagnosis.red_flags,
                recommended_tests=diagnosis.recommended_tests,
                recommended_treatments=diagnosis.recommended_treatments,
                follow_up_instructions=diagnosis.follow_up_instructions,
                evidence_used=diagnosis.evidence_used,
                guidelines_applied=diagnosis.guidelines_applied,
                citation_count=diagnosis.citation_count,
                rag_enabled=diagnosis.rag_enabled,
                processing_time_ms=diagnosis.processing_time_ms,
                confidence_level=_calculate_confidence_level(diagnosis.differential_diagnoses),
                created_at=diagnosis.created_at,
                lab_results_parsed=diagnosis.lab_results_parsed or None,
                lab_abnormalities=diagnosis.lab_abnormalities or None,
            )
            response_list.append(response)
        
        logger.info(
            "diagnoses_searched",
            results_count=len(response_list),
            correlation_id=correlation_id,
        )
        
        return response_list
        
    except Exception as e:
        logger.error("search_error", error=str(e), correlation_id=correlation_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search diagnoses"
        )


@diagnosis_router.get("/export-csv")
async def export_diagnoses_csv(
    # Same filters as search
    query: Optional[str] = None,
    patient_id: Optional[str] = None,
    disease: Optional[str] = None,
    confidence_level: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
    request: Request = None,
):
    """Export filtered diagnoses to CSV."""
    correlation_id = get_correlation_id(request)
    
    try:
        import csv
        import io
        from datetime import datetime
        
        # Reuse search logic (without pagination)
        from sqlalchemy import or_, and_, func
        
        query_builder = select(Diagnosis).where(
            and_(
                Diagnosis.doctor_id == current_doctor.id,
                Diagnosis.is_active == True
            )
        )
        
        # Apply same filters
        if query:
            query_lower = f"%{query.lower()}%"
            query_builder = query_builder.where(
                or_(
                    func.lower(Diagnosis.chief_complaint).like(query_lower),
                    func.cast(Diagnosis.symptoms, String).like(query_lower),
                    func.cast(Diagnosis.differential_diagnoses, String).like(query_lower),
                )
            )
        
        if patient_id:
            query_builder = query_builder.where(Diagnosis.patient_id == patient_id)
        
        if disease:
            disease_lower = f"%{disease.lower()}%"
            query_builder = query_builder.where(
                func.cast(Diagnosis.differential_diagnoses, String).like(disease_lower)
            )
        
        if date_from:
            date_from_obj = datetime.fromisoformat(date_from)
            query_builder = query_builder.where(Diagnosis.created_at >= date_from_obj)
        
        if date_to:
            date_to_obj = datetime.fromisoformat(date_to)
            query_builder = query_builder.where(Diagnosis.created_at <= date_to_obj)
        
        query_builder = query_builder.order_by(Diagnosis.created_at.desc())
        
        result = await db.execute(query_builder)
        diagnoses = result.scalars().all()
        
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            'Date',
            'Patient ID',
            'Chief Complaint',
            'Top Diagnosis',
            'Confidence',
            'ICD-10',
            'Confidence Level',
            'Citations',
            'RAG Enabled',
            'Processing Time (ms)',
        ])
        
        # Data
        for diagnosis in diagnoses:
            top_dx = diagnosis.differential_diagnoses[0] if diagnosis.differential_diagnoses else {}
            
            writer.writerow([
                diagnosis.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                diagnosis.patient_id,
                diagnosis.chief_complaint,
                top_dx.get('diagnosis', 'N/A'),
                f"{top_dx.get('confidence', 0) * 100:.1f}%",
                top_dx.get('icd10_code', 'N/A'),
                _calculate_confidence_level(diagnosis.differential_diagnoses),
                diagnosis.citation_count,
                'Yes' if diagnosis.rag_enabled else 'No',
                f"{diagnosis.processing_time_ms:.0f}",
            ])
        
        # Return CSV file
        csv_content = output.getvalue()
        output.close()
        
        filename = f"diagnoses_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return StreamingResponse(
            io.BytesIO(csv_content.encode('utf-8')),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except Exception as e:
        logger.error("csv_export_error", error=str(e), correlation_id=correlation_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export CSV"
        )


@diagnosis_router.get("/analytics-by-type")
async def get_analytics_by_diagnosis_type(
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
    request: Request = None,
):
    """Get analytics grouped by diagnosis type."""
    correlation_id = get_correlation_id(request)
    
    try:
        from collections import defaultdict
        
        # Get all diagnoses
        result = await db.execute(
            select(Diagnosis).where(
                and_(
                    Diagnosis.doctor_id == current_doctor.id,
                    Diagnosis.is_active == True
                )
            )
        )
        diagnoses = result.scalars().all()
        
        # Group by diagnosis type
        diagnosis_stats = defaultdict(lambda: {
            'count': 0,
            'total_citations': 0,
            'avg_confidence': 0,
            'confidence_sum': 0,
            'with_feedback': 0,
            'accurate_count': 0,
        })
        
        for diagnosis in diagnoses:
            if diagnosis.differential_diagnoses and len(diagnosis.differential_diagnoses) > 0:
                top_dx = diagnosis.differential_diagnoses[0]['diagnosis']
                
                diagnosis_stats[top_dx]['count'] += 1
                diagnosis_stats[top_dx]['total_citations'] += diagnosis.citation_count or 0
                diagnosis_stats[top_dx]['confidence_sum'] += diagnosis.differential_diagnoses[0].get('confidence', 0)
        
        # Get feedback data
        feedback_result = await db.execute(
            select(DoctorFeedback).where(DoctorFeedback.doctor_id == current_doctor.id)
        )
        feedbacks = feedback_result.scalars().all()
        
        # Map feedback to diagnoses
        for feedback in feedbacks:
            diagnosis_result = await db.execute(
                select(Diagnosis).where(Diagnosis.id == feedback.diagnosis_id)
            )
            diagnosis = diagnosis_result.scalar_one_or_none()
            
            if diagnosis and diagnosis.differential_diagnoses:
                top_dx = diagnosis.differential_diagnoses[0]['diagnosis']
                
                if top_dx in diagnosis_stats:
                    diagnosis_stats[top_dx]['with_feedback'] += 1
                    
                    if feedback.was_in_top_5:
                        diagnosis_stats[top_dx]['accurate_count'] += 1
        
        # Calculate averages
        analytics = []
        for diagnosis_type, stats in diagnosis_stats.items():
            if stats['count'] > 0:
                analytics.append({
                    'diagnosis': diagnosis_type,
                    'count': stats['count'],
                    'avg_confidence': (stats['confidence_sum'] / stats['count']) * 100,
                    'avg_citations': stats['total_citations'] / stats['count'],
                    'accuracy_rate': (stats['accurate_count'] / stats['with_feedback'] * 100) if stats['with_feedback'] > 0 else None,
                    'feedback_count': stats['with_feedback'],
                })
        
        # Sort by count
        analytics.sort(key=lambda x: x['count'], reverse=True)
        
        logger.info(
            "diagnosis_type_analytics_generated",
            types_count=len(analytics),
            correlation_id=correlation_id,
        )
        
        return {
            'total_diagnosis_types': len(analytics),
            'analytics': analytics[:20],  # Top 20
        }
        
    except Exception as e:
        logger.error("analytics_by_type_error", error=str(e), correlation_id=correlation_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate analytics"
        )
    

@diagnosis_router.get("/{diagnosis_id}", response_model=DiagnosisResponseWithEvidence)
async def get_diagnosis(
    diagnosis_id: str,
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
    request: Request = None,
):
    """Get diagnosis by ID."""
    correlation_id = get_correlation_id(request)
    
    try:
        # Get diagnosis
        result = await db.execute(
            select(Diagnosis).where(
                Diagnosis.id == diagnosis_id,
                Diagnosis.doctor_id == current_doctor.id
            )
        )
        diagnosis = result.scalar_one_or_none()
        
        if not diagnosis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Diagnosis not found"
            )
        
        # Build response (same as analyze_symptoms)
        differential_diagnoses_with_evidence = []
        
        for dx in diagnosis.differential_diagnoses:
            citations_list = []
            if diagnosis.evidence_used:
                for evidence in diagnosis.evidence_used[:3]:
                    citations_list.append({
                        "pubmed_id": evidence.get("pubmed_id"),
                        "title": evidence.get("title", ""),
                        "authors": evidence.get("authors", ""),
                        "journal": evidence.get("journal", ""),
                        "publication_year": evidence.get("publication_year"),
                        "doi": evidence.get("doi"),
                        "citation_text": evidence.get("citation_text", ""),
                        "relevance_score": evidence.get("relevance_score", 0.9),
                        "evidence_type": evidence.get("evidence_type", "research"),
                        "abstract": evidence.get("abstract", ""),
                        "url": evidence.get("url", ""),
                    })
            
            dx_with_evidence = DifferentialDiagnosisWithEvidence(
                diagnosis=dx.get("diagnosis"),
                confidence=dx.get("confidence"),
                icd10_code=dx.get("icd10_code"),
                reasoning=dx.get("reasoning"),
                supporting_evidence=dx.get("supporting_evidence", []),
                contradicting_factors=dx.get("contradicting_factors"),
                rank=dx.get("rank"),
                citations=citations_list,
                evidence_quality=_calculate_evidence_quality(citations_list),
            )
            
            differential_diagnoses_with_evidence.append(dx_with_evidence)
        
        response = DiagnosisResponseWithEvidence(
            id=diagnosis.id,
            patient_id=diagnosis.patient_id,
            correlation_id=diagnosis.correlation_id,
            chief_complaint=diagnosis.chief_complaint,
            symptoms=diagnosis.symptoms,
            differential_diagnoses=differential_diagnoses_with_evidence,
            clinical_reasoning=diagnosis.clinical_reasoning,
            missing_information=diagnosis.missing_information,
            red_flags=diagnosis.red_flags,
            recommended_tests=diagnosis.recommended_tests,
            recommended_treatments=diagnosis.recommended_treatments,
            follow_up_instructions=diagnosis.follow_up_instructions,
            evidence_used=diagnosis.evidence_used,
            guidelines_applied=diagnosis.guidelines_applied,
            citation_count=diagnosis.citation_count,
            rag_enabled=diagnosis.rag_enabled,
            processing_time_ms=diagnosis.processing_time_ms,
            confidence_level=_calculate_confidence_level(diagnosis.differential_diagnoses),
            created_at=diagnosis.created_at,
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_diagnosis_error", error=str(e), correlation_id=correlation_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve diagnosis"
        )
    
@diagnosis_router.get("/patient/{patient_id}/history", response_model=List[DiagnosisResponseWithEvidence])
async def get_patient_diagnosis_history(
    patient_id: str,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
    request: Request = None,
):
    """Get all diagnoses for a patient."""
    correlation_id = get_correlation_id(request)
    
    try:
        result = await db.execute(
            select(Diagnosis)
            .where(
                Diagnosis.patient_id == patient_id,
                Diagnosis.doctor_id == current_doctor.id
            )
            .order_by(Diagnosis.created_at.desc())
            .limit(limit)
        )
        diagnoses = result.scalars().all()
        
        # Build response for each diagnosis
        response_list = []
        for diagnosis in diagnoses:
            differential_diagnoses_with_evidence = []
            
            for dx in diagnosis.differential_diagnoses:
                citations_list = []
                if diagnosis.evidence_used:
                    for evidence in diagnosis.evidence_used[:3]:
                        citations_list.append({
                            "pubmed_id": evidence.get("pubmed_id"),
                            "title": evidence.get("title", ""),
                            "authors": evidence.get("authors", ""),
                            "journal": evidence.get("journal", ""),
                            "publication_year": evidence.get("publication_year"),
                            "doi": evidence.get("doi"),
                            "citation_text": evidence.get("citation_text", ""),
                            "relevance_score": evidence.get("relevance_score", 0.9),
                            "evidence_type": evidence.get("evidence_type", "research"),
                            "abstract": evidence.get("abstract", ""),
                            "url": evidence.get("url", ""),
                        })
                
                dx_with_evidence = DifferentialDiagnosisWithEvidence(
                    diagnosis=dx.get("diagnosis"),
                    confidence=dx.get("confidence"),
                    icd10_code=dx.get("icd10_code"),
                    reasoning=dx.get("reasoning"),
                    supporting_evidence=dx.get("supporting_evidence", []),
                    contradicting_factors=dx.get("contradicting_factors"),
                    rank=dx.get("rank"),
                    citations=citations_list,
                    evidence_quality=_calculate_evidence_quality(citations_list),
                )
                differential_diagnoses_with_evidence.append(dx_with_evidence)
            
            response = DiagnosisResponseWithEvidence(
                id=diagnosis.id,
                patient_id=diagnosis.patient_id,
                correlation_id=diagnosis.correlation_id,
                chief_complaint=diagnosis.chief_complaint,
                symptoms=diagnosis.symptoms,
                differential_diagnoses=differential_diagnoses_with_evidence,
                clinical_reasoning=diagnosis.clinical_reasoning,
                missing_information=diagnosis.missing_information,
                red_flags=diagnosis.red_flags,
                recommended_tests=diagnosis.recommended_tests,
                recommended_treatments=diagnosis.recommended_treatments,
                follow_up_instructions=diagnosis.follow_up_instructions,
                evidence_used=diagnosis.evidence_used,
                guidelines_applied=diagnosis.guidelines_applied,
                citation_count=diagnosis.citation_count,
                rag_enabled=diagnosis.rag_enabled,
                processing_time_ms=diagnosis.processing_time_ms,
                confidence_level=_calculate_confidence_level(diagnosis.differential_diagnoses),
                created_at=diagnosis.created_at,
            )
            response_list.append(response)
        
        return response_list
        
    except Exception as e:
        logger.error("get_patient_history_error", error=str(e), correlation_id=correlation_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve diagnosis history"
        )


@diagnosis_router.post("/upload-lab-report")
async def upload_lab_report(
    file: UploadFile = File(...),
    current_doctor: Doctor = Depends(get_current_doctor),
    request: Request = None,
):
    """Upload and parse lab report file."""
    correlation_id = get_correlation_id(request)
    
    try:
        from app.services.ocr_service import ocr_service
        from app.services.lab_parser_service import lab_parser_service
        
        # Validate file type
        allowed_types = ['image/png', 'image/jpeg', 'application/pdf', 
                        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                        'text/plain']
        
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: {file.content_type}"
            )
        
        # Read file
        file_bytes = await file.read()
        
        logger.info(
            "lab_report_upload",
            filename=file.filename,
            file_size=len(file_bytes),
            correlation_id=correlation_id,
        )
        
        # Extract text
        extracted_text = ocr_service.extract_text(file_bytes, file.filename)
        
        # Parse lab results
        parsed = lab_parser_service.parse_lab_text(extracted_text)
        
        return {
            "extracted_text": extracted_text,
            "parsed_results": parsed.get("parsed_results", {}),
            "abnormalities": parsed.get("abnormalities", []),
            "total_tests": parsed.get("total_tests", 0),
            "abnormal_count": parsed.get("abnormal_count", 0),
        }
        
    except Exception as e:
        logger.error("lab_report_upload_error", error=str(e), correlation_id=correlation_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process lab report: {str(e)}"
        )

@diagnosis_router.get("/{diagnosis_id}/export-pdf")
async def export_diagnosis_pdf(
    diagnosis_id: str,
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
    request: Request = None,
):
    """Export diagnosis as PDF report."""
    correlation_id = get_correlation_id(request)
    
    try:
        # Get diagnosis
        result = await db.execute(
            select(Diagnosis).where(
                Diagnosis.id == diagnosis_id,
                Diagnosis.doctor_id == current_doctor.id
            )
        )
        diagnosis = result.scalar_one_or_none()
        
        if not diagnosis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Diagnosis not found"
            )
        
        # Get patient
        patient_result = await db.execute(
            select(Patient).where(Patient.id == diagnosis.patient_id)
        )
        patient = patient_result.scalar_one()
        
        # Prepare data for PDF
        diagnosis_data = {
            'id': diagnosis.id,
            'chief_complaint': diagnosis.chief_complaint,
            'symptoms': diagnosis.symptoms,
            'differential_diagnoses': diagnosis.differential_diagnoses,
            'clinical_reasoning': diagnosis.clinical_reasoning,
            'recommended_tests': diagnosis.recommended_tests,
            'recommended_treatments': diagnosis.recommended_treatments,
            'red_flags': diagnosis.red_flags,
            'follow_up_instructions': diagnosis.follow_up_instructions,
            'rag_enabled': diagnosis.rag_enabled,
            'citation_count': diagnosis.citation_count,
            'lab_results_parsed': diagnosis.lab_results_parsed,
            'lab_abnormalities': diagnosis.lab_abnormalities,
            'created_at': diagnosis.created_at,
        }
        
        patient_data = {
            'full_name': patient.full_name,
            'mrn': patient.mrn,
            'date_of_birth': str(patient.date_of_birth),
            'gender': patient.gender,
            'blood_group': patient.blood_group,
            'allergies': patient.allergies,
        }
        
        doctor_data = {
            'full_name': current_doctor.full_name,
            'license_number': current_doctor.license_number,
            'specialization': current_doctor.specialization,
        }
        
        # Generate PDF
        pdf_bytes = pdf_service.generate_diagnosis_report(
            diagnosis=diagnosis_data,
            patient=patient_data,
            doctor=doctor_data
        )
        
        # Return as downloadable file
        filename = f"Report_{patient.full_name.replace(' ', '_')}_{patient.mrn}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"

        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("pdf_export_error", error=str(e), correlation_id=correlation_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate PDF report"
        )


@diagnosis_router.post("/{diagnosis_id}/email-pdf")
async def email_diagnosis_pdf(
    diagnosis_id: str,
    recipient_email: EmailStr,
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
    request: Request = None,
):
    """Email diagnosis PDF report."""
    correlation_id = get_correlation_id(request)
    
    try:
        # Get diagnosis and patient (same as export endpoint)
        result = await db.execute(
            select(Diagnosis).where(
                Diagnosis.id == diagnosis_id,
                Diagnosis.doctor_id == current_doctor.id
            )
        )
        diagnosis = result.scalar_one_or_none()
        
        if not diagnosis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Diagnosis not found"
            )
        
        patient_result = await db.execute(
            select(Patient).where(Patient.id == diagnosis.patient_id)
        )
        patient = patient_result.scalar_one()
        
        # Prepare data
        diagnosis_data = {
            'id': diagnosis.id,
            'chief_complaint': diagnosis.chief_complaint,
            'symptoms': diagnosis.symptoms,
            'differential_diagnoses': diagnosis.differential_diagnoses,
            'clinical_reasoning': diagnosis.clinical_reasoning,
            'recommended_tests': diagnosis.recommended_tests,
            'recommended_treatments': diagnosis.recommended_treatments,
            'red_flags': diagnosis.red_flags,
            'follow_up_instructions': diagnosis.follow_up_instructions,
            'rag_enabled': diagnosis.rag_enabled,
            'citation_count': diagnosis.citation_count,
            'lab_results_parsed': diagnosis.lab_results_parsed,
            'lab_abnormalities': diagnosis.lab_abnormalities,
            'created_at': diagnosis.created_at,
        }
        
        patient_data = {
            'full_name': patient.full_name,
            'mrn': patient.mrn,
            'date_of_birth': str(patient.date_of_birth),
            'gender': patient.gender,
            'blood_group': patient.blood_group,
            'allergies': patient.allergies,
        }
        
        doctor_data = {
            'full_name': current_doctor.full_name,
            'license_number': current_doctor.license_number,
            'specialization': current_doctor.specialization,
        }
        
        # Generate PDF
        pdf_bytes = pdf_service.generate_diagnosis_report(
            diagnosis=diagnosis_data,
            patient=patient_data,
            doctor=doctor_data
        )
        
        # Send email
        success = pdf_service.email_diagnosis_report(
            pdf_bytes=pdf_bytes,
            recipient_email=recipient_email,
            patient_name=patient.full_name,
            doctor_name=current_doctor.full_name
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send email"
            )
        
        return {"message": f"Report emailed successfully to {recipient_email}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("email_pdf_error", error=str(e), correlation_id=correlation_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to email report"
        )

@diagnosis_router.post("/compare")
async def compare_diagnoses(
    diagnosis_ids: List[str],
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
    request: Request = None,
):
    """Compare multiple diagnoses side-by-side."""
    correlation_id = get_correlation_id(request)
    
    try:
        if len(diagnosis_ids) < 2 or len(diagnosis_ids) > 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please select 2-3 diagnoses to compare"
            )
        
        # Fetch all diagnoses
        diagnoses = []
        for diagnosis_id in diagnosis_ids:
            result = await db.execute(
                select(Diagnosis).where(
                    Diagnosis.id == diagnosis_id,
                    Diagnosis.doctor_id == current_doctor.id
                )
            )
            diagnosis = result.scalar_one_or_none()
            if not diagnosis:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Diagnosis {diagnosis_id} not found"
                )
            diagnoses.append(diagnosis)
        
        # Sort by date
        diagnoses.sort(key=lambda d: d.created_at)
        
        # Build comparison response
        comparison = {
            "diagnosis_count": len(diagnoses),
            "patient_id": diagnoses[0].patient_id,
            "date_range": {
                "start": diagnoses[0].created_at,
                "end": diagnoses[-1].created_at,
            },
            "diagnoses": [],
        }
        
        for idx, diagnosis in enumerate(diagnoses):
            comparison["diagnoses"].append({
                "id": diagnosis.id,
                "sequence": idx + 1,
                "date": diagnosis.created_at,
                "chief_complaint": diagnosis.chief_complaint,
                "symptoms": diagnosis.symptoms,
                "differential_diagnoses": diagnosis.differential_diagnoses,
                "clinical_reasoning": diagnosis.clinical_reasoning,
                "recommended_tests": diagnosis.recommended_tests,
                "recommended_treatments": diagnosis.recommended_treatments,
                "red_flags": diagnosis.red_flags,
                "lab_results_parsed": diagnosis.lab_results_parsed,
                "lab_abnormalities": diagnosis.lab_abnormalities,
                "confidence_level": _calculate_confidence_level(diagnosis.differential_diagnoses),
                "rag_enabled": diagnosis.rag_enabled,
                "citation_count": diagnosis.citation_count,
            })
        
        # Calculate changes between diagnoses
        comparison["changes"] = _calculate_diagnosis_changes(diagnoses)
        
        logger.info(
            "diagnoses_compared",
            count=len(diagnoses),
            correlation_id=correlation_id,
        )
        
        return comparison
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("comparison_error", error=str(e), correlation_id=correlation_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compare diagnoses"
        )
    
def _calculate_diagnosis_changes(diagnoses: List[Diagnosis]) -> Dict[str, Any]:
    """Calculate what changed between diagnoses."""
    changes = {
        "symptom_changes": [],
        "lab_changes": [],
        "diagnosis_changes": [],
        "overall_trend": "",
    }
    
    for i in range(1, len(diagnoses)):
        prev = diagnoses[i-1]
        curr = diagnoses[i]
        
        # Symptom changes
        prev_symptoms = {s.get('name'): s for s in prev.symptoms}
        curr_symptoms = {s.get('name'): s for s in curr.symptoms}
        
        # New symptoms
        new_symptoms = set(curr_symptoms.keys()) - set(prev_symptoms.keys())
        if new_symptoms:
            changes["symptom_changes"].append({
                "from_date": prev.created_at,
                "to_date": curr.created_at,
                "type": "new",
                "symptoms": list(new_symptoms),
            })
        
        # Resolved symptoms
        resolved = set(prev_symptoms.keys()) - set(curr_symptoms.keys())
        if resolved:
            changes["symptom_changes"].append({
                "from_date": prev.created_at,
                "to_date": curr.created_at,
                "type": "resolved",
                "symptoms": list(resolved),
            })
        
        # Lab changes
        if prev.lab_results_parsed and curr.lab_results_parsed:
            for test_key in prev.lab_results_parsed.keys():
                if test_key in curr.lab_results_parsed:
                    prev_val = prev.lab_results_parsed[test_key]['value']
                    curr_val = curr.lab_results_parsed[test_key]['value']
                    
                    if abs(curr_val - prev_val) / prev_val > 0.1:  # >10% change
                        changes["lab_changes"].append({
                            "test": prev.lab_results_parsed[test_key]['name'],
                            "from_value": prev_val,
                            "to_value": curr_val,
                            "change_percent": ((curr_val - prev_val) / prev_val) * 100,
                            "from_date": prev.created_at,
                            "to_date": curr.created_at,
                        })
        
        # Top diagnosis changes
        prev_top = prev.differential_diagnoses[0]['diagnosis'] if prev.differential_diagnoses else None
        curr_top = curr.differential_diagnoses[0]['diagnosis'] if curr.differential_diagnoses else None
        
        if prev_top != curr_top:
            changes["diagnosis_changes"].append({
                "from_diagnosis": prev_top,
                "to_diagnosis": curr_top,
                "from_date": prev.created_at,
                "to_date": curr.created_at,
            })
    
    # Overall trend
    if len(changes["symptom_changes"]) > 0:
        resolved_count = sum(1 for c in changes["symptom_changes"] if c["type"] == "resolved")
        new_count = sum(1 for c in changes["symptom_changes"] if c["type"] == "new")
        
        if resolved_count > new_count:
            changes["overall_trend"] = "improving"
        elif new_count > resolved_count:
            changes["overall_trend"] = "worsening"
        else:
            changes["overall_trend"] = "stable"
    else:
        changes["overall_trend"] = "stable"
    
    return changes
    
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