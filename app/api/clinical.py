"""
Clinical API Routes - Notes, Vitals, Appointments, Profile
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional
from datetime import datetime

from app.core.database import get_db
from app.api.dependencies import get_current_doctor
from app.models.models import Doctor, ClinicalNote, VitalRecord, Appointment
from app.schemas.schemas import (
    ClinicalNoteCreate, ClinicalNoteUpdate, ClinicalNoteResponse,
    VitalRecordCreate, VitalRecordResponse,
    AppointmentCreate, AppointmentUpdate, AppointmentResponse,
    DoctorProfileUpdate, DoctorSettingsUpdate, DoctorProfileResponse,
)
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


def get_correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", "")


# ==================== DOCTOR PROFILE ====================

@router.get("/profile", response_model=DoctorProfileResponse)
async def get_profile(
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
    request: Request = None,
):
    """Get doctor profile."""
    return current_doctor


@router.patch("/profile", response_model=DoctorProfileResponse)
async def update_profile(
    profile_update: DoctorProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
    request: Request = None,
):
    """Update doctor profile."""
    try:
        update_data = profile_update.dict(exclude_unset=True)
        for key, value in update_data.items():
            if hasattr(current_doctor, key):
                setattr(current_doctor, key, value)
        
        await db.commit()
        await db.refresh(current_doctor)
        
        logger.info("profile_updated", doctor_id=current_doctor.id)
        return current_doctor
        
    except Exception as e:
        await db.rollback()
        logger.error("profile_update_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to update profile")


@router.patch("/settings", response_model=DoctorProfileResponse)
async def update_settings(
    settings_update: DoctorSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
    request: Request = None,
):
    """Update doctor settings."""
    try:
        update_data = settings_update.dict(exclude_unset=True)
        for key, value in update_data.items():
            if hasattr(current_doctor, key):
                setattr(current_doctor, key, value)
        
        await db.commit()
        await db.refresh(current_doctor)
        
        logger.info("settings_updated", doctor_id=current_doctor.id)
        return current_doctor
        
    except Exception as e:
        await db.rollback()
        logger.error("settings_update_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to update settings")


@router.post("/change-password")
async def change_password(
    current_password: str,
    new_password: str,
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
    request: Request = None,
):
    """Change doctor password."""
    try:
        from app.core.security import verify_password, get_password_hash
        
        if not verify_password(current_password, current_doctor.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        current_doctor.hashed_password = get_password_hash(new_password)
        await db.commit()
        
        logger.info("password_changed", doctor_id=current_doctor.id)
        return {"message": "Password changed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("password_change_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to change password")


# ==================== CLINICAL NOTES ====================

@router.post("/notes", response_model=ClinicalNoteResponse, status_code=201)
async def create_note(
    note: ClinicalNoteCreate,
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
    request: Request = None,
):
    """Create clinical note."""
    try:
        new_note = ClinicalNote(
            patient_id=note.patient_id,
            doctor_id=current_doctor.id,
            diagnosis_id=note.diagnosis_id,
            title=note.title,
            content=note.content,
            note_type=note.note_type,
            is_private=note.is_private,
        )
        
        db.add(new_note)
        await db.commit()
        await db.refresh(new_note)
        
        logger.info("clinical_note_created", note_id=new_note.id)
        return new_note
        
    except Exception as e:
        await db.rollback()
        logger.error("note_creation_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create note")


@router.get("/notes/patient/{patient_id}", response_model=List[ClinicalNoteResponse])
async def get_patient_notes(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
    request: Request = None,
):
    """Get all clinical notes for a patient."""
    try:
        result = await db.execute(
            select(ClinicalNote).where(
                and_(
                    ClinicalNote.patient_id == patient_id,
                    ClinicalNote.doctor_id == current_doctor.id,
                )
            ).order_by(ClinicalNote.created_at.desc())
        )
        return result.scalars().all()
        
    except Exception as e:
        logger.error("get_notes_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get notes")


@router.patch("/notes/{note_id}", response_model=ClinicalNoteResponse)
async def update_note(
    note_id: str,
    note_update: ClinicalNoteUpdate,
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
    request: Request = None,
):
    """Update clinical note."""
    try:
        result = await db.execute(
            select(ClinicalNote).where(
                and_(
                    ClinicalNote.id == note_id,
                    ClinicalNote.doctor_id == current_doctor.id,
                )
            )
        )
        note = result.scalar_one_or_none()
        
        if not note:
            raise HTTPException(status_code=404, detail="Note not found")
        
        update_data = note_update.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(note, key, value)
        
        note.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(note)
        
        return note
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("note_update_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to update note")


@router.delete("/notes/{note_id}")
async def delete_note(
    note_id: str,
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
    request: Request = None,
):
    """Delete clinical note."""
    try:
        result = await db.execute(
            select(ClinicalNote).where(
                and_(
                    ClinicalNote.id == note_id,
                    ClinicalNote.doctor_id == current_doctor.id,
                )
            )
        )
        note = result.scalar_one_or_none()
        
        if not note:
            raise HTTPException(status_code=404, detail="Note not found")
        
        await db.delete(note)
        await db.commit()
        
        return {"message": "Note deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("note_delete_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to delete note")


# ==================== VITAL RECORDS ====================

@router.post("/vitals", response_model=VitalRecordResponse, status_code=201)
async def create_vital_record(
    vitals: VitalRecordCreate,
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
    request: Request = None,
):
    """Record vital signs."""
    try:
        # Calculate BMI if weight and height provided
        bmi = None
        if vitals.weight and vitals.height:
            height_m = vitals.height / 100
            bmi = round(vitals.weight / (height_m ** 2), 1)
        
        vital_record = VitalRecord(
            patient_id=vitals.patient_id,
            doctor_id=current_doctor.id,
            diagnosis_id=vitals.diagnosis_id,
            temperature=vitals.temperature,
            blood_pressure_systolic=vitals.blood_pressure_systolic,
            blood_pressure_diastolic=vitals.blood_pressure_diastolic,
            heart_rate=vitals.heart_rate,
            respiratory_rate=vitals.respiratory_rate,
            oxygen_saturation=vitals.oxygen_saturation,
            weight=vitals.weight,
            height=vitals.height,
            bmi=bmi,
            blood_glucose=vitals.blood_glucose,
            notes=vitals.notes,
            recorded_at=vitals.recorded_at or datetime.utcnow(),
        )
        
        db.add(vital_record)
        await db.commit()
        await db.refresh(vital_record)
        
        logger.info("vital_record_created", record_id=vital_record.id)
        return vital_record
        
    except Exception as e:
        await db.rollback()
        logger.error("vital_record_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to record vitals")


@router.get("/vitals/patient/{patient_id}", response_model=List[VitalRecordResponse])
async def get_patient_vitals(
    patient_id: str,
    limit: int = 30,
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
    request: Request = None,
):
    """Get vital records for patient."""
    try:
        result = await db.execute(
            select(VitalRecord).where(
                and_(
                    VitalRecord.patient_id == patient_id,
                    VitalRecord.doctor_id == current_doctor.id,
                )
            ).order_by(VitalRecord.recorded_at.desc()).limit(limit)
        )
        return result.scalars().all()
        
    except Exception as e:
        logger.error("get_vitals_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get vitals")


# ==================== APPOINTMENTS ====================

@router.post("/appointments", response_model=AppointmentResponse, status_code=201)
async def create_appointment(
    appointment: AppointmentCreate,
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
    request: Request = None,
):
    """Create appointment."""
    try:
        new_appointment = Appointment(
            patient_id=appointment.patient_id,
            doctor_id=current_doctor.id,
            diagnosis_id=appointment.diagnosis_id,
            title=appointment.title,
            appointment_type=appointment.appointment_type,
            scheduled_at=appointment.scheduled_at,
            duration_minutes=appointment.duration_minutes,
            notes=appointment.notes,
        )
        
        db.add(new_appointment)
        await db.commit()
        await db.refresh(new_appointment)
        
        logger.info("appointment_created", appointment_id=new_appointment.id)
        return new_appointment
        
    except Exception as e:
        await db.rollback()
        logger.error("appointment_creation_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create appointment")


@router.get("/appointments", response_model=List[AppointmentResponse])
async def get_appointments(
    status: Optional[str] = None,
    upcoming_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
    request: Request = None,
):
    """Get all appointments for doctor."""
    try:
        query = select(Appointment).where(
            Appointment.doctor_id == current_doctor.id
        )
        
        if status:
            query = query.where(Appointment.status == status)
        
        if upcoming_only:
            query = query.where(Appointment.scheduled_at >= datetime.utcnow())
        
        query = query.order_by(Appointment.scheduled_at.asc())
        
        result = await db.execute(query)
        return result.scalars().all()
        
    except Exception as e:
        logger.error("get_appointments_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get appointments")


@router.get("/appointments/patient/{patient_id}", response_model=List[AppointmentResponse])
async def get_patient_appointments(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
    request: Request = None,
):
    """Get appointments for patient."""
    try:
        result = await db.execute(
            select(Appointment).where(
                and_(
                    Appointment.patient_id == patient_id,
                    Appointment.doctor_id == current_doctor.id,
                )
            ).order_by(Appointment.scheduled_at.asc())
        )
        return result.scalars().all()
        
    except Exception as e:
        logger.error("get_patient_appointments_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get appointments")


@router.patch("/appointments/{appointment_id}", response_model=AppointmentResponse)
async def update_appointment(
    appointment_id: str,
    appointment_update: AppointmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
    request: Request = None,
):
    """Update appointment."""
    try:
        result = await db.execute(
            select(Appointment).where(
                and_(
                    Appointment.id == appointment_id,
                    Appointment.doctor_id == current_doctor.id,
                )
            )
        )
        appointment = result.scalar_one_or_none()
        
        if not appointment:
            raise HTTPException(status_code=404, detail="Appointment not found")
        
        update_data = appointment_update.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(appointment, key, value)
        
        appointment.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(appointment)
        
        return appointment
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("appointment_update_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to update appointment")


@router.delete("/appointments/{appointment_id}")
async def delete_appointment(
    appointment_id: str,
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
    request: Request = None,
):
    """Delete appointment."""
    try:
        result = await db.execute(
            select(Appointment).where(
                and_(
                    Appointment.id == appointment_id,
                    Appointment.doctor_id == current_doctor.id,
                )
            )
        )
        appointment = result.scalar_one_or_none()
        
        if not appointment:
            raise HTTPException(status_code=404, detail="Appointment not found")
        
        await db.delete(appointment)
        await db.commit()
        
        return {"message": "Appointment deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("appointment_delete_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to delete appointment")