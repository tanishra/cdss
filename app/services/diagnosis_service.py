"""
Diagnosis Service Module - Following SOLID Principles
Single Responsibility: Manage diagnosis workflow
"""
from typing import Dict, Any
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.models.models import Patient, Diagnosis
from app.services.llm_service import llm_service, LLMServiceError
from app.schemas.schemas import DiagnosisRequest
from app.core.logging import get_logger, audit_logger

logger = get_logger(__name__)


class DiagnosisServiceError(Exception):
    """Custom exception for diagnosis service."""
    pass


class DiagnosisService:
    """
    Diagnosis Service
    Single Responsibility: Orchestrate diagnosis creation workflow
    """
    
    async def create_diagnosis(
        self,
        db: AsyncSession,
        request: DiagnosisRequest,
        doctor_id: str,
        correlation_id: str,
    ) -> Diagnosis:
        """
        Create diagnosis with AI analysis.
        
        Follows Single Responsibility: Each step is delegated
        """
        try:
            # Step 1: Validate and get patient
            patient = await self._get_patient(db, request.patient_id, doctor_id)
            
            # Step 2: Calculate patient age
            patient_age = self._calculate_age(patient.date_of_birth)
            
            # Step 3: Prepare medical history
            medical_history = self._prepare_medical_history(patient)
            
            # Step 4: Generate diagnosis via LLM
            logger.info(
                "diagnosis_generation_start",
                patient_id=request.patient_id,
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
                correlation_id=correlation_id,
            )
            
            # Step 5: Create diagnosis record
            diagnosis = await self._create_diagnosis_record(
                db, request, doctor_id, correlation_id, llm_result
            )
            
            # Step 6: Audit logging
            await self._log_diagnosis(
                patient_id=request.patient_id,
                doctor_id=doctor_id,
                llm_result=llm_result,
                correlation_id=correlation_id,
            )
            
            logger.info(
                "diagnosis_created",
                diagnosis_id=diagnosis.id,
                correlation_id=correlation_id,
            )
            
            return diagnosis
            
        except LLMServiceError as e:
            logger.error("llm_service_error", error=str(e), correlation_id=correlation_id)
            raise DiagnosisServiceError(f"Failed to generate diagnosis: {str(e)}") from e
        except Exception as e:
            logger.error("diagnosis_creation_error", error=str(e), correlation_id=correlation_id)
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
    ) -> Diagnosis:
        """Create diagnosis database record."""
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
            # Metadata
            processing_time_ms=llm_result["metadata"]["processing_time_ms"],
            llm_model_used=llm_result["metadata"]["model"],
            llm_tokens_used=llm_result["metadata"]["tokens_used"],
        )
        
        db.add(diagnosis)
        await db.commit()
        await db.refresh(diagnosis)
        
        return diagnosis
    
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