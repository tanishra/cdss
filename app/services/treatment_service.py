"""
Treatment Service
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime, timedelta
import random

from app.models.models import Treatment, Prescription, Patient
from app.services.drug_interaction_service import drug_interaction_service
from app.core.logging import get_logger

logger = get_logger(__name__)


class TreatmentServiceError(Exception):
    """Treatment service error."""
    pass


class TreatmentService:
    """Service for managing treatments and prescriptions."""
    
    async def create_treatment(
        self,
        db: AsyncSession,
        treatment_data: Dict[str, Any],
        patient_id: str,
        doctor_id: str,
        correlation_id: str = "",
    ) -> Treatment:
        """Create new treatment record."""
        try:
            # Get patient for interaction check
            patient_result = await db.execute(
                select(Patient).where(Patient.id == patient_id)
            )
            patient = patient_result.scalar_one()
            
            # Check drug interactions if medication
            interaction_check = {"has_interactions": False, "warnings": []}
            
            if treatment_data.get("medication_name"):
                current_meds = [m.get("name") for m in patient.medications] if patient.medications else []
                allergies = patient.allergies or []
                
                interaction_check = drug_interaction_service.check_interactions(
                    new_medication=treatment_data["medication_name"],
                    current_medications=current_meds,
                    allergies=allergies,
                )
            
            # Create treatment
            treatment = Treatment(
                diagnosis_id=treatment_data["diagnosis_id"],
                patient_id=patient_id,
                doctor_id=doctor_id,
                treatment_type=treatment_data["treatment_type"],
                medication_name=treatment_data.get("medication_name"),
                dosage=treatment_data.get("dosage"),
                frequency=treatment_data.get("frequency"),
                route=treatment_data.get("route"),
                duration=treatment_data.get("duration"),
                instructions=treatment_data.get("instructions"),
                start_date=treatment_data.get("start_date") or datetime.utcnow(),
                end_date=treatment_data.get("end_date"),
                has_interactions=interaction_check["has_interactions"],
                interaction_warnings=interaction_check["warnings"],
            )
            
            db.add(treatment)
            await db.commit()
            await db.refresh(treatment)
            
            logger.info(
                "treatment_created",
                treatment_id=treatment.id,
                patient_id=patient_id,
                has_interactions=interaction_check["has_interactions"],
                correlation_id=correlation_id,
            )
            
            return treatment
            
        except Exception as e:
            await db.rollback()
            logger.error("treatment_creation_error", error=str(e), correlation_id=correlation_id)
            raise TreatmentServiceError(f"Failed to create treatment: {str(e)}") from e
    
    async def update_treatment(
        self,
        db: AsyncSession,
        treatment_id: str,
        update_data: Dict[str, Any],
        doctor_id: str,
        correlation_id: str = "",
    ) -> Treatment:
        """Update treatment outcome."""
        try:
            result = await db.execute(
                select(Treatment).where(
                    and_(
                        Treatment.id == treatment_id,
                        Treatment.doctor_id == doctor_id
                    )
                )
            )
            treatment = result.scalar_one_or_none()
            
            if not treatment:
                raise TreatmentServiceError("Treatment not found")
            
            # Update fields
            for key, value in update_data.items():
                if hasattr(treatment, key) and value is not None:
                    setattr(treatment, key, value)
            
            treatment.updated_at = datetime.utcnow()
            
            await db.commit()
            await db.refresh(treatment)
            
            logger.info(
                "treatment_updated",
                treatment_id=treatment_id,
                correlation_id=correlation_id,
            )
            
            return treatment
            
        except Exception as e:
            await db.rollback()
            logger.error("treatment_update_error", error=str(e), correlation_id=correlation_id)
            raise TreatmentServiceError(f"Failed to update treatment: {str(e)}") from e
    
    async def get_patient_treatments(
        self,
        db: AsyncSession,
        patient_id: str,
        doctor_id: str,
        active_only: bool = False,
        correlation_id: str = "",
    ) -> List[Treatment]:
        """Get all treatments for a patient."""
        try:
            query = select(Treatment).where(
                and_(
                    Treatment.patient_id == patient_id,
                    Treatment.doctor_id == doctor_id,
                    Treatment.is_active == True
                )
            )
            
            if active_only:
                query = query.where(Treatment.status == "active")
            
            query = query.order_by(Treatment.created_at.desc())
            
            result = await db.execute(query)
            treatments = result.scalars().all()
            
            logger.info(
                "treatments_retrieved",
                patient_id=patient_id,
                count=len(treatments),
                correlation_id=correlation_id,
            )
            
            return treatments
            
        except Exception as e:
            logger.error("get_treatments_error", error=str(e), correlation_id=correlation_id)
            raise TreatmentServiceError(f"Failed to get treatments: {str(e)}") from e
    
    async def create_prescription(
        self,
        db: AsyncSession,
        prescription_data: Dict[str, Any],
        doctor_id: str,
        correlation_id: str = "",
    ) -> Prescription:
        """Create prescription."""
        try:
            # Generate prescription number
            prescription_number = f"RX{datetime.now().strftime('%Y%m%d')}{random.randint(1000, 9999)}"
            
            # Calculate valid until date
            valid_days = prescription_data.get("valid_days", 30)
            valid_until = datetime.utcnow() + timedelta(days=valid_days)
            
            prescription = Prescription(
                patient_id=prescription_data["patient_id"],
                doctor_id=doctor_id,
                diagnosis_id=prescription_data.get("diagnosis_id"),
                prescription_number=prescription_number,
                date_issued=datetime.utcnow(),
                valid_until=valid_until,
                medications=prescription_data["medications"],
                diagnosis_summary=prescription_data.get("diagnosis_summary"),
                special_instructions=prescription_data.get("special_instructions"),
                refills_allowed=prescription_data.get("refills_allowed", 0),
            )
            
            db.add(prescription)
            await db.commit()
            await db.refresh(prescription)
            
            logger.info(
                "prescription_created",
                prescription_id=prescription.id,
                prescription_number=prescription_number,
                correlation_id=correlation_id,
            )
            
            return prescription
            
        except Exception as e:
            await db.rollback()
            logger.error("prescription_creation_error", error=str(e), correlation_id=correlation_id)
            raise TreatmentServiceError(f"Failed to create prescription: {str(e)}") from e
    
    async def get_treatment_analytics(
        self,
        db: AsyncSession,
        doctor_id: str,
        correlation_id: str = "",
    ) -> Dict[str, Any]:
        """Get treatment effectiveness analytics."""
        try:
            # Get all treatments
            result = await db.execute(
                select(Treatment).where(
                    and_(
                        Treatment.doctor_id == doctor_id,
                        Treatment.is_active == True
                    )
                )
            )
            treatments = result.scalars().all()
            
            # Calculate metrics
            total = len(treatments)
            if total == 0:
                return {"total_treatments": 0}
            
            effective = sum(1 for t in treatments if t.effectiveness == "effective")
            partially_effective = sum(1 for t in treatments if t.effectiveness == "partially_effective")
            ineffective = sum(1 for t in treatments if t.effectiveness == "ineffective")
            
            active = sum(1 for t in treatments if t.status == "active")
            completed = sum(1 for t in treatments if t.status == "completed")
            discontinued = sum(1 for t in treatments if t.status == "discontinued")
            
            # Side effects
            total_side_effects = sum(len(t.side_effects or []) for t in treatments)
            
            analytics = {
                "total_treatments": total,
                "effectiveness": {
                    "effective": effective,
                    "effective_percentage": (effective / total) * 100 if total > 0 else 0,
                    "partially_effective": partially_effective,
                    "ineffective": ineffective,
                },
                "status": {
                    "active": active,
                    "completed": completed,
                    "discontinued": discontinued,
                },
                "side_effects_reported": total_side_effects,
                "interaction_warnings": sum(1 for t in treatments if t.has_interactions),
            }
            
            logger.info(
                "treatment_analytics_generated",
                total_treatments=total,
                correlation_id=correlation_id,
            )
            
            return analytics
            
        except Exception as e:
            logger.error("analytics_error", error=str(e), correlation_id=correlation_id)
            raise TreatmentServiceError(f"Failed to generate analytics: {str(e)}") from e


# Global instance
treatment_service = TreatmentService()