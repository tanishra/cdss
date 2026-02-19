"""
Patient Portal API Routes
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List

from app.core.database import get_db
from app.api.patient_auth import get_current_patient_user
from app.models.models import (
    PatientUser, Patient, Diagnosis, Appointment, 
    VitalRecord, ClinicalNote, Treatment, PatientMessage, Doctor
)
from app.schemas.schemas import (
    PatientMessageCreate, PatientMessageResponse
)
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


def get_correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", "")


@router.get("/profile")
async def get_patient_profile(
    db: AsyncSession = Depends(get_db),
    current_user: PatientUser = Depends(get_current_patient_user),
):
    """Get patient profile."""
    try:
        result = await db.execute(
            select(Patient).where(Patient.id == current_user.patient_id)
        )
        patient = result.scalar_one_or_none()
        
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        
        return {
            "id": patient.id,
            "mrn": patient.mrn,
            "full_name": patient.full_name,
            "date_of_birth": patient.date_of_birth,
            "gender": patient.gender,
            "phone": patient.phone,
            "email": patient.email,
            "blood_group": patient.blood_group,
            "allergies": patient.allergies,
            "chronic_conditions": patient.chronic_conditions,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_patient_profile_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get profile")


@router.get("/diagnoses")
async def get_patient_diagnoses(
    db: AsyncSession = Depends(get_db),
    current_user: PatientUser = Depends(get_current_patient_user),
):
    """Get patient diagnoses."""
    try:
        result = await db.execute(
            select(Diagnosis).where(Diagnosis.patient_id == current_user.patient_id)
            .order_by(Diagnosis.created_at.desc())
        )
        diagnoses = result.scalars().all()
        
        return [
            {
                "id": d.id,
                "chief_complaint": d.chief_complaint,
                "created_at": d.created_at,
                "top_diagnosis": d.differential_diagnoses[0]['diagnosis'] if d.differential_diagnoses else None,
                "confidence": d.differential_diagnoses[0]['confidence'] if d.differential_diagnoses else None,
            }
            for d in diagnoses
        ]
        
    except Exception as e:
        logger.error("get_patient_diagnoses_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get diagnoses")


@router.get("/diagnoses/{diagnosis_id}")
async def get_diagnosis_detail(
    diagnosis_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: PatientUser = Depends(get_current_patient_user),
):
    """Get diagnosis details."""
    try:
        result = await db.execute(
            select(Diagnosis).where(
                and_(
                    Diagnosis.id == diagnosis_id,
                    Diagnosis.patient_id == current_user.patient_id
                )
            )
        )
        diagnosis = result.scalar_one_or_none()
        
        if not diagnosis:
            raise HTTPException(status_code=404, detail="Diagnosis not found")
        
        return {
            "id": diagnosis.id,
            "chief_complaint": diagnosis.chief_complaint,
            "symptoms": diagnosis.symptoms,
            "differential_diagnoses": diagnosis.differential_diagnoses,
            "recommended_tests": diagnosis.recommended_tests,
            "recommended_treatments": diagnosis.recommended_treatments,
            "follow_up_instructions": diagnosis.follow_up_instructions,
            "created_at": diagnosis.created_at,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_diagnosis_detail_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get diagnosis")


@router.get("/appointments")
async def get_patient_appointments(
    db: AsyncSession = Depends(get_db),
    current_user: PatientUser = Depends(get_current_patient_user),
):
    """Get patient appointments."""
    try:
        result = await db.execute(
            select(Appointment).where(Appointment.patient_id == current_user.patient_id)
            .order_by(Appointment.scheduled_at.desc())
        )
        appointments = result.scalars().all()
        
        return [
            {
                "id": apt.id,
                "title": apt.title,
                "appointment_type": apt.appointment_type,
                "scheduled_at": apt.scheduled_at,
                "duration_minutes": apt.duration_minutes,
                "status": apt.status,
                "notes": apt.notes,
            }
            for apt in appointments
        ]
        
    except Exception as e:
        logger.error("get_patient_appointments_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get appointments")


@router.get("/vitals")
async def get_patient_vitals(
    db: AsyncSession = Depends(get_db),
    current_user: PatientUser = Depends(get_current_patient_user),
):
    """Get patient vital records."""
    try:
        result = await db.execute(
            select(VitalRecord).where(VitalRecord.patient_id == current_user.patient_id)
            .order_by(VitalRecord.recorded_at.desc()).limit(30)
        )
        vitals = result.scalars().all()
        
        return [
            {
                "id": v.id,
                "temperature": v.temperature,
                "blood_pressure_systolic": v.blood_pressure_systolic,
                "blood_pressure_diastolic": v.blood_pressure_diastolic,
                "heart_rate": v.heart_rate,
                "oxygen_saturation": v.oxygen_saturation,
                "weight": v.weight,
                "bmi": v.bmi,
                "blood_glucose": v.blood_glucose,
                "recorded_at": v.recorded_at,
            }
            for v in vitals
        ]
        
    except Exception as e:
        logger.error("get_patient_vitals_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get vitals")


@router.get("/treatments")
async def get_patient_treatments(
    db: AsyncSession = Depends(get_db),
    current_user: PatientUser = Depends(get_current_patient_user),
):
    """Get patient treatments."""
    try:
        result = await db.execute(
            select(Treatment).where(Treatment.patient_id == current_user.patient_id)
            .order_by(Treatment.created_at.desc())
        )
        treatments = result.scalars().all()
        
        return [
            {
                "id": t.id,
                "medication_name": t.medication_name,
                "dosage": t.dosage,
                "frequency": t.frequency,
                "route": t.route,
                "status": t.status,
                "start_date": t.start_date,
                "instructions": t.instructions,
            }
            for t in treatments
        ]
        
    except Exception as e:
        logger.error("get_patient_treatments_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get treatments")


# ==================== MESSAGES ====================

@router.post("/messages", response_model=PatientMessageResponse)
async def send_message_to_doctor(
    message: PatientMessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: PatientUser = Depends(get_current_patient_user),
):
    """Send message to doctor."""
    try:
        new_message = PatientMessage(
            patient_id=current_user.patient_id,
            doctor_id=message.doctor_id,
            subject=message.subject,
            message=message.message,
            sender_type="patient",
            is_read=False,
        )
        
        db.add(new_message)
        await db.commit()
        await db.refresh(new_message)
        
        logger.info("patient_message_sent", message_id=new_message.id)
        return new_message
        
    except Exception as e:
        await db.rollback()
        logger.error("send_message_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to send message")


@router.get("/messages", response_model=List[PatientMessageResponse])
async def get_patient_messages(
    db: AsyncSession = Depends(get_db),
    current_user: PatientUser = Depends(get_current_patient_user),
):
    """Get patient messages."""
    try:
        result = await db.execute(
            select(PatientMessage).where(
                PatientMessage.patient_id == current_user.patient_id
            ).order_by(PatientMessage.created_at.desc())
        )
        return result.scalars().all()
        
    except Exception as e:
        logger.error("get_messages_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get messages")


@router.get("/doctors")
async def get_patient_doctors(
    db: AsyncSession = Depends(get_db),
    current_user: PatientUser = Depends(get_current_patient_user),
):
    """Get doctors who have treated this patient."""
    try:
        # Get unique doctors from diagnoses
        result = await db.execute(
            select(Diagnosis.doctor_id).where(
                Diagnosis.patient_id == current_user.patient_id
            ).distinct()
        )
        doctor_ids = [row[0] for row in result]
        
        if not doctor_ids:
            return []
        
        doctors_result = await db.execute(
            select(Doctor).where(Doctor.id.in_(doctor_ids))
        )
        doctors = doctors_result.scalars().all()
        
        return [
            {
                "id": doc.id,
                "full_name": doc.full_name,
                "specialization": doc.specialization,
                "email": doc.email,
            }
            for doc in doctors
        ]
        
    except Exception as e:
        logger.error("get_patient_doctors_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get doctors")