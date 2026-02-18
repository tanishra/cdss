"""
Activity API Routes - Recent Activity Tracking
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List

from app.core.database import get_db
from app.api.dependencies import get_current_doctor
from app.models.models import Doctor, Diagnosis, Appointment, ClinicalNote
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


def get_correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", "")


@router.get("/recent")
async def get_recent_activity(
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
    request: Request = None,
):
    """Get recent activity for dashboard."""
    try:
        # Recent diagnoses
        diagnoses_result = await db.execute(
            select(Diagnosis).where(Diagnosis.doctor_id == current_doctor.id)
            .order_by(Diagnosis.created_at.desc()).limit(5)
        )
        diagnoses = diagnoses_result.scalars().all()
        
        # Recent appointments
        appointments_result = await db.execute(
            select(Appointment).where(Appointment.doctor_id == current_doctor.id)
            .order_by(Appointment.created_at.desc()).limit(5)
        )
        appointments = appointments_result.scalars().all()
        
        # Recent notes
        notes_result = await db.execute(
            select(ClinicalNote).where(ClinicalNote.doctor_id == current_doctor.id)
            .order_by(ClinicalNote.created_at.desc()).limit(5)
        )
        notes = notes_result.scalars().all()
        
        return {
            "diagnoses": [
                {
                    "id": d.id,
                    "patient_id": d.patient_id,
                    "chief_complaint": d.chief_complaint,
                    "created_at": d.created_at,
                    "top_diagnosis": d.differential_diagnoses[0]['diagnosis'] if d.differential_diagnoses else None,
                }
                for d in diagnoses
            ],
            "appointments": [
                {
                    "id": a.id,
                    "patient_id": a.patient_id,
                    "title": a.title,
                    "scheduled_at": a.scheduled_at,
                    "status": a.status,
                }
                for a in appointments
            ],
            "notes": [
                {
                    "id": n.id,
                    "patient_id": n.patient_id,
                    "title": n.title,
                    "created_at": n.created_at,
                }
                for n in notes
            ],
        }
        
    except Exception as e:
        logger.error("recent_activity_error", error=str(e))
        return {"diagnoses": [], "appointments": [], "notes": []}