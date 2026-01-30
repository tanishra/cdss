"""
Patient Service Module - Following SOLID Principles
Single Responsibility: Patient management only
"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.models.models import Patient
from app.schemas.schemas import PatientCreate
from app.core.logging import get_logger, audit_logger

logger = get_logger(__name__)


class PatientServiceError(Exception):
    """Custom exception for patient service."""
    pass


class PatientService:
    """
    Patient Service
    Single Responsibility: Manage patient operations
    """
    
    async def create_patient(
        self,
        db: AsyncSession,
        patient_data: PatientCreate,
        doctor_id: str,
        correlation_id: str,
    ) -> Patient:
        """Create new patient."""
        try:
            # Check for duplicate MRN
            await self._validate_unique_mrn(db, patient_data.mrn)
            
            # Create patient record
            patient = self._build_patient_model(patient_data, doctor_id)
            
            db.add(patient)
            await db.commit()
            await db.refresh(patient)
            
            # Audit logging
            audit_logger.log_patient_access(
                patient_id=patient.id,
                doctor_id=doctor_id,
                action="create",
                correlation_id=correlation_id,
            )
            
            logger.info(
                "patient_created",
                patient_id=patient.id,
                mrn=patient.mrn,
                correlation_id=correlation_id,
            )
            
            return patient
            
        except PatientServiceError:
            raise
        except Exception as e:
            logger.error("patient_creation_error", error=str(e), correlation_id=correlation_id)
            raise PatientServiceError(f"Failed to create patient: {str(e)}") from e
    
    async def get_patient(
        self,
        db: AsyncSession,
        patient_id: str,
        doctor_id: str,
        correlation_id: str,
    ) -> Optional[Patient]:
        """Get patient by ID with access control."""
        try:
            result = await db.execute(
                select(Patient).where(
                    Patient.id == patient_id,
                    Patient.doctor_id == doctor_id,
                    Patient.is_active == True,
                )
            )
            patient = result.scalar_one_or_none()
            
            if patient:
                audit_logger.log_patient_access(
                    patient_id=patient_id,
                    doctor_id=doctor_id,
                    action="read",
                    correlation_id=correlation_id,
                )
            
            return patient
            
        except Exception as e:
            logger.error("patient_retrieval_error", error=str(e), correlation_id=correlation_id)
            raise PatientServiceError(f"Failed to retrieve patient: {str(e)}") from e
    
    async def _validate_unique_mrn(self, db: AsyncSession, mrn: str) -> None:
        """Validate MRN uniqueness."""
        result = await db.execute(select(Patient).where(Patient.mrn == mrn))
        if result.scalar_one_or_none():
            raise PatientServiceError(f"Patient with MRN {mrn} already exists")
    
    def _build_patient_model(self, patient_data: PatientCreate, doctor_id: str) -> Patient:
        """Build patient model from data."""
        return Patient(
            id=str(uuid.uuid4()),
            doctor_id=doctor_id,
            mrn=patient_data.mrn,
            full_name=patient_data.full_name,
            date_of_birth=patient_data.date_of_birth,
            gender=patient_data.gender.value,
            blood_group=patient_data.blood_group,
            phone=patient_data.phone,
            email=patient_data.email,
            address=patient_data.address,
            allergies=patient_data.allergies,
            chronic_conditions=patient_data.chronic_conditions,
            medications=patient_data.medications,
            family_history=patient_data.family_history,
            surgical_history=patient_data.surgical_history,
            smoking_status=patient_data.smoking_status.value if patient_data.smoking_status else None,
            alcohol_consumption=patient_data.alcohol_consumption.value if patient_data.alcohol_consumption else None,
            notes=patient_data.notes,
        )


# Global instance
patient_service = PatientService()