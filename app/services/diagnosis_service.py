"""
Diagnosis Service Module - with RAG Integration
"""
from typing import Dict, Any
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
import time

from app.models.models import Patient, Diagnosis, Citation
from app.services.llm_service import llm_service, LLMServiceError
from app.services.rag_service import rag_service, RAGServiceError
from app.services.lab_parser_service import lab_parser_service
from app.schemas.schemas import DiagnosisRequest
from app.core.config import settings
from app.core.logging import get_logger, audit_logger

logger = get_logger(__name__)


class DiagnosisServiceError(Exception):
    """Custom exception for diagnosis service."""
    pass


class DiagnosisService:
    """
    Diagnosis Service - UPDATED with RAG
    """
    
    async def create_diagnosis(
        self,
        db: AsyncSession,
        request: DiagnosisRequest,
        doctor_id: str,
        correlation_id: str,
    ) -> Diagnosis:
        """
        Create diagnosis with RAG-enhanced AI analysis.
        """
        start_time = time.time()
        
        try:
            # Step 1: Validate and get patient
            patient = await self._get_patient(db, request.patient_id, doctor_id)
            
            # Step 2: Calculate patient age
            patient_age = self._calculate_age(patient.date_of_birth)
            
            # Step 3: Prepare medical history
            medical_history = self._prepare_medical_history(patient)
            
            # Step 4: Parse lab results if provided - MOVE THIS HERE
            parsed_labs = None
            lab_abnormalities = None
            if request.lab_results_input:
                if request.lab_results_input.format == "json":
                    parsed = lab_parser_service.parse_lab_json(request.lab_results_input.data)
                else:
                    parsed = lab_parser_service.parse_lab_text(request.lab_results_input.data)
            
                parsed_labs = parsed.get("parsed_results")
                lab_abnormalities = parsed.get("abnormalities")
            
                # Add lab interpretation to medical history
                if lab_abnormalities:
                    lab_interpretation = lab_parser_service.get_clinical_interpretation(lab_abnormalities)
                    medical_history["lab_interpretation"] = lab_interpretation
                    medical_history["lab_abnormalities"] = lab_abnormalities
    
                logger.info(
                    "lab_results_parsed",
                    total_tests=parsed.get("total_tests", 0),
                    abnormal_count=parsed.get("abnormal_count", 0),
                    correlation_id=correlation_id,
                    )
                    
            # Step 5: Retrieve evidence using RAG (if enabled)
            evidence_data = None
            if settings.ENABLE_RAG:
                try:
                    logger.info(
                        "rag_evidence_retrieval_starting",
                        patient_id=request.patient_id,
                        correlation_id=correlation_id,
                    )
                    
                    # Extract symptom names for RAG
                    symptom_names = [s.name for s in request.symptoms]
                    
                    evidence_data = await rag_service.retrieve_evidence(
                        chief_complaint=request.chief_complaint,
                        symptoms=symptom_names,
                        patient_age=patient_age,
                        patient_gender=patient.gender,
                        medical_history=medical_history,
                        db=db,
                        correlation_id=correlation_id,
                    )
                    
                    logger.info(
                        "rag_evidence_retrieved",
                        evidence_count=len(evidence_data.get("evidence", [])),
                        correlation_id=correlation_id,
                    )
                    
                except RAGServiceError as e:
                    logger.warning(
                        "rag_retrieval_failed_continuing_without",
                        error=str(e),
                        correlation_id=correlation_id,
                    )
                    evidence_data = None
            
            # Step 5: Generate diagnosis via LLM (with or without evidence)
            logger.info(
                "diagnosis_generation_start",
                patient_id=request.patient_id,
                rag_enabled=evidence_data is not None,
                correlation_id=correlation_id,
            )
            
            llm_result = await llm_service.generate_differential_diagnosis(
                chief_complaint=request.chief_complaint,
                symptoms=request.symptoms,
                patient_age=patient_age,
                patient_gender=patient.gender,
                medical_history=medical_history,
                vital_signs=request.vital_signs,
                lab_results=request.lab_results,
                evidence=evidence_data,  # NEW: Pass evidence to LLM
                correlation_id=correlation_id,
            )
            
            # Step 6: Create diagnosis record
            diagnosis = await self._create_diagnosis_record(
                db=db,
                request=request,
                doctor_id=doctor_id,
                correlation_id=correlation_id,
                llm_result=llm_result,
                evidence_data=evidence_data,
            )
            
            # Step 7: Create citation records (if evidence was used)
            if evidence_data and evidence_data.get("evidence"):
                await self._create_citation_records(
                    db=db,
                    diagnosis=diagnosis,
                    evidence=evidence_data["evidence"],
                    llm_result=llm_result,
                )
            
            # Step 8: Add to db and commit all changes
            db.add(diagnosis)
            await db.commit()
            # await db.refresh(diagnosis)
            
            # Step 9: Audit logging
            await self._log_diagnosis(
                patient_id=request.patient_id,
                doctor_id=doctor_id,
                llm_result=llm_result,
                correlation_id=correlation_id,
            )
            
            processing_time = (time.time() - start_time) * 1000
            
            logger.info(
                "diagnosis_created_with_rag",
                diagnosis_id=diagnosis.id,
                rag_enabled=diagnosis.rag_enabled,
                citation_count=diagnosis.citation_count,
                total_processing_time_ms=processing_time,
                correlation_id=correlation_id,
            )
            
            return diagnosis
            
        except LLMServiceError as e:
            logger.error("llm_service_error", error=str(e), correlation_id=correlation_id)
            raise DiagnosisServiceError(f"Failed to generate diagnosis: {str(e)}") from e
        except Exception as e:
            logger.error(
                "diagnosis_creation_error",
                error=str(e),
                error_type=type(e).__name__,
                correlation_id=correlation_id,
            )
            raise DiagnosisServiceError(f"Failed to create diagnosis: {str(e)}") from e
    
    async def _get_patient(
        self, db: AsyncSession, patient_id: str, doctor_id: str
    ) -> Patient:
        """Get patient with access validation."""
        result = await db.execute(
            select(Patient).where(
                Patient.id == patient_id,
                Patient.doctor_id == doctor_id,
                Patient.is_active == True,
            )
        )
        patient = result.scalar_one_or_none()
        
        if not patient:
            raise DiagnosisServiceError(f"Patient not found: {patient_id}")
        
        return patient
    
    def _calculate_age(self, date_of_birth: date) -> int:
        """Calculate age from date of birth."""
        today = datetime.now().date()
        age = today.year - date_of_birth.year
        if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
            age -= 1
        return age
    
    def _prepare_medical_history(self, patient: Patient) -> Dict[str, Any]:
        """Prepare medical history dictionary."""
        return {
            "chronic_conditions": patient.chronic_conditions or [],
            "allergies": patient.allergies or [],
            "medications": patient.medications or [],
        }
    
    async def _create_diagnosis_record(
        self,
        db: AsyncSession,
        request: DiagnosisRequest,
        doctor_id: str,
        correlation_id: str,
        llm_result: Dict[str, Any],
        evidence_data: Dict[str, Any] = None,
    ) -> Diagnosis:
        """Create diagnosis database record with RAG data."""
        diagnosis = Diagnosis(
            id=str(uuid.uuid4()),
            patient_id=request.patient_id,
            doctor_id=doctor_id,
            correlation_id=correlation_id,
            chief_complaint=request.chief_complaint,
            symptoms=[s.dict() for s in request.symptoms],
            symptom_duration=request.symptom_duration,
            symptom_severity=request.symptom_severity.value if request.symptom_severity else None,
            # Vital signs
            temperature=request.vital_signs.temperature if request.vital_signs else None,
            blood_pressure_systolic=request.vital_signs.blood_pressure_systolic if request.vital_signs else None,
            blood_pressure_diastolic=request.vital_signs.blood_pressure_diastolic if request.vital_signs else None,
            heart_rate=request.vital_signs.heart_rate if request.vital_signs else None,
            respiratory_rate=request.vital_signs.respiratory_rate if request.vital_signs else None,
            oxygen_saturation=request.vital_signs.oxygen_saturation if request.vital_signs else None,
            # Lab data
            lab_results=request.lab_results,
            imaging_findings=request.imaging_findings,
            # LLM results
            differential_diagnoses=llm_result["differential_diagnoses"],
            clinical_reasoning=llm_result["clinical_reasoning"],
            missing_information=llm_result.get("missing_information"),
            red_flags=llm_result.get("red_flags"),
            recommended_tests=llm_result.get("recommended_tests"),
            recommended_treatments=llm_result.get("recommended_treatments"),
            follow_up_instructions=llm_result.get("follow_up_instructions"),
            # RAG-specific fields
            evidence_used=evidence_data.get("evidence", [])[:5] if evidence_data else None,
            guidelines_applied=[
                e.get("title") for e in evidence_data.get("evidence", [])
                if e.get("evidence_type") == "guideline"
            ] if evidence_data else None,
            rag_enabled=evidence_data is not None,
            citation_count=0,  # Will be updated after citations are created
            # Metadata
            processing_time_ms=llm_result["metadata"]["processing_time_ms"],
            llm_model_used=llm_result["metadata"]["model"],
            llm_tokens_used=llm_result["metadata"]["tokens_used"],
            lab_results_raw=request.lab_results_input.data if request.lab_results_input else None,
            # lab_results_parsed=parsed_labs,
            # lab_abnormalities=lab_abnormalities,
        )
        
        db.add(diagnosis)
        return diagnosis
    
    async def _create_citation_records(
        self,
        db: AsyncSession,
        diagnosis: Diagnosis,
        evidence: list,
        llm_result: Dict[str, Any],
    ):
        """Create citation records for diagnosis."""
        citations_created = 0
        
        # Map evidence to diagnoses (top 3 citations per diagnosis)
        for dx in llm_result["differential_diagnoses"][:3]:  # Top 3 diagnoses
            diagnosis_name = dx.get("diagnosis")
            
            # Get relevant evidence for this diagnosis
            relevant_evidence = evidence[:settings.MAX_CITATIONS_PER_DIAGNOSIS]
            
            for article in relevant_evidence:
                citation = Citation(
                    id=str(uuid.uuid4()),
                    diagnosis_id=diagnosis.id,
                    pubmed_id=article.get("pubmed_id"),
                    title=article.get("title", "Unknown"),
                    authors=article.get("authors"),
                    journal=article.get("journal"),
                    publication_year=article.get("publication_year"),
                    doi=article.get("doi"),
                    citation_text=self._format_citation(article),
                    relevance_score=article.get("relevance_score", 0.5),
                    evidence_type=article.get("evidence_type", "research"),
                    abstract=article.get("abstract"),
                    url=article.get("url"),
                    diagnosis_name=diagnosis_name,
                )
                
                db.add(citation)
                citations_created += 1
        
        # Update diagnosis citation count
        diagnosis.citation_count = citations_created
    
    def _format_citation(self, article: Dict[str, Any]) -> str:
        """Format citation in APA style."""
        authors = article.get("authors", "Unknown authors")
        year = article.get("publication_year", "n.d.")
        title = article.get("title", "Unknown title")
        journal = article.get("journal", "")
        
        citation = f"{authors} ({year}). {title}."
        if journal:
            citation += f" {journal}."
        
        return citation
    
    async def _log_diagnosis(
        self,
        patient_id: str,
        doctor_id: str,
        llm_result: Dict[str, Any],
        correlation_id: str,
    ) -> None:
        """Log diagnosis to audit trail."""
        audit_logger.log_diagnosis(
            patient_id=patient_id,
            doctor_id=doctor_id,
            diagnoses=[d["diagnosis"] for d in llm_result["differential_diagnoses"]],
            confidence_scores=[d["confidence"] for d in llm_result["differential_diagnoses"]],
            duration_ms=llm_result["metadata"]["processing_time_ms"],
            correlation_id=correlation_id,
        )


# Global instance
diagnosis_service = DiagnosisService()