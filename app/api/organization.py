"""
Organization API Routes - Multi-tenant management
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from typing import List

from app.core.database import get_db
from app.api.dependencies import get_current_doctor
from app.models.models import Doctor, Organization, Department, Patient
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


def get_correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", "")


def require_admin(current_doctor: Doctor):
    """Ensure user is admin."""
    if not current_doctor.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )


# ==================== ORGANIZATION ====================

@router.get("/")
async def get_organization(
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
):
    """Get current organization details."""
    try:
        if not current_doctor.organization_id:
            raise HTTPException(status_code=404, detail="No organization assigned")
        
        result = await db.execute(
            select(Organization).where(Organization.id == current_doctor.organization_id)
        )
        org = result.scalar_one_or_none()
        
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        
        # Get counts
        doctors_count = await db.execute(
            select(func.count(Doctor.id)).where(Doctor.organization_id == org.id)
        )
        patients_count = await db.execute(
            select(func.count(Patient.id)).where(Patient.organization_id == org.id)
        )
        departments_count = await db.execute(
            select(func.count(Department.id)).where(Department.organization_id == org.id)
        )
        
        return {
            "id": org.id,
            "name": org.name,
            "org_type": org.org_type,
            "address": org.address,
            "phone": org.phone,
            "email": org.email,
            "website": org.website,
            "is_active": org.is_active,
            "plan": org.plan,
            "max_doctors": org.max_doctors,
            "max_patients": org.max_patients,
            "created_at": org.created_at,
            "stats": {
                "doctors": doctors_count.scalar(),
                "patients": patients_count.scalar(),
                "departments": departments_count.scalar(),
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_organization_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get organization")


@router.patch("/")
async def update_organization(
    name: str = None,
    address: str = None,
    phone: str = None,
    email: str = None,
    website: str = None,
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
):
    """Update organization (admin only)."""
    try:
        require_admin(current_doctor)
        
        result = await db.execute(
            select(Organization).where(Organization.id == current_doctor.organization_id)
        )
        org = result.scalar_one_or_none()
        
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        
        if name: org.name = name
        if address: org.address = address
        if phone: org.phone = phone
        if email: org.email = email
        if website: org.website = website
        
        await db.commit()
        await db.refresh(org)
        
        return {"message": "Organization updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("update_organization_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to update organization")


# ==================== DEPARTMENTS ====================

@router.post("/departments")
async def create_department(
    name: str,
    description: str = None,
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
):
    """Create department (admin only)."""
    try:
        require_admin(current_doctor)
        
        department = Department(
            organization_id=current_doctor.organization_id,
            name=name,
            description=description,
            is_active=True,
        )
        
        db.add(department)
        await db.commit()
        await db.refresh(department)
        
        return {
            "id": department.id,
            "name": department.name,
            "description": department.description,
            "created_at": department.created_at,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("create_department_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create department")


@router.get("/departments")
async def list_departments(
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
):
    """List all departments."""
    try:
        result = await db.execute(
            select(Department).where(
                and_(
                    Department.organization_id == current_doctor.organization_id,
                    Department.is_active == True
                )
            ).order_by(Department.name)
        )
        departments = result.scalars().all()
        
        dept_list = []
        for dept in departments:
            # Count doctors
            doctor_count = await db.execute(
                select(func.count(Doctor.id)).where(Doctor.department_id == dept.id)
            )
            
            dept_list.append({
                "id": dept.id,
                "name": dept.name,
                "description": dept.description,
                "doctor_count": doctor_count.scalar(),
                "created_at": dept.created_at,
            })
        
        return dept_list
        
    except Exception as e:
        logger.error("list_departments_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list departments")


# ==================== DOCTORS MANAGEMENT ====================

@router.get("/doctors")
async def list_doctors(
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
):
    """List all doctors in organization."""
    try:
        result = await db.execute(
            select(Doctor).where(
                and_(
                    Doctor.organization_id == current_doctor.organization_id,
                    Doctor.is_active == True
                )
            ).order_by(Doctor.full_name)
        )
        doctors = result.scalars().all()
        
        return [
            {
                "id": doc.id,
                "full_name": doc.full_name,
                "email": doc.email,
                "specialization": doc.specialization,
                "is_admin": doc.is_admin,
                "department_id": doc.department_id,
                "created_at": doc.created_at,
            }
            for doc in doctors
        ]
        
    except Exception as e:
        logger.error("list_doctors_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list doctors")


@router.post("/doctors/invite")
async def invite_doctor(
    email: str,
    full_name: str,
    specialization: str,
    department_id: str = None,
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
):
    """Invite new doctor to organization (admin only)."""
    try:
        require_admin(current_doctor)
        from app.core.security import get_password_hash
        from app.models.models import Role
        
        # Check email
        result = await db.execute(select(Doctor).where(Doctor.email == email))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already exists")
        
        # Get doctor role
        role_result = await db.execute(select(Role).where(Role.name == "doctor"))
        doctor_role = role_result.scalar_one()
        
        # Create temporary password (should send email in production)
        temp_password = f"temp{email[:4]}{123}"  # Simple temp password
        
        new_doctor = Doctor(
            email=email,
            hashed_password=get_password_hash(temp_password),
            full_name=full_name,
            specialization=specialization,
            organization_id=current_doctor.organization_id,
            department_id=department_id,
            role_id=doctor_role.id,
            is_admin=False,
            is_active=True,
        )
        
        db.add(new_doctor)
        await db.commit()
        await db.refresh(new_doctor)
        
        logger.info("doctor_invited", doctor_id=new_doctor.id, invited_by=current_doctor.id)
        
        return {
            "message": "Doctor invited successfully",
            "doctor_id": new_doctor.id,
            "temp_password": temp_password,  # In production, send via email
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("invite_doctor_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to invite doctor")


@router.patch("/doctors/{doctor_id}/department")
async def assign_department(
    doctor_id: str,
    department_id: str,
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
):
    """Assign doctor to department (admin only)."""
    try:
        require_admin(current_doctor)
        
        result = await db.execute(
            select(Doctor).where(
                and_(
                    Doctor.id == doctor_id,
                    Doctor.organization_id == current_doctor.organization_id
                )
            )
        )
        doctor = result.scalar_one_or_none()
        
        if not doctor:
            raise HTTPException(status_code=404, detail="Doctor not found")
        
        doctor.department_id = department_id
        await db.commit()
        
        return {"message": "Department assigned successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("assign_department_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to assign department")


@router.delete("/doctors/{doctor_id}")
async def deactivate_doctor(
    doctor_id: str,
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
):
    """Deactivate doctor (admin only)."""
    try:
        require_admin(current_doctor)
        
        if doctor_id == current_doctor.id:
            raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
        
        result = await db.execute(
            select(Doctor).where(
                and_(
                    Doctor.id == doctor_id,
                    Doctor.organization_id == current_doctor.organization_id
                )
            )
        )
        doctor = result.scalar_one_or_none()
        
        if not doctor:
            raise HTTPException(status_code=404, detail="Doctor not found")
        
        doctor.is_active = False
        await db.commit()
        
        return {"message": "Doctor deactivated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("deactivate_doctor_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to deactivate doctor")


# ==================== PATIENTS ASSIGNMENT ====================

@router.patch("/patients/{patient_id}/assign")
async def assign_patient(
    patient_id: str,
    doctor_id: str,
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
):
    """Assign patient to doctor (admin only)."""
    try:
        require_admin(current_doctor)
        
        # Get patient
        patient_result = await db.execute(
            select(Patient).where(
                and_(
                    Patient.id == patient_id,
                    Patient.organization_id == current_doctor.organization_id
                )
            )
        )
        patient = patient_result.scalar_one_or_none()
        
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        
        # Verify doctor in same org
        doctor_result = await db.execute(
            select(Doctor).where(
                and_(
                    Doctor.id == doctor_id,
                    Doctor.organization_id == current_doctor.organization_id
                )
            )
        )
        doctor = doctor_result.scalar_one_or_none()
        
        if not doctor:
            raise HTTPException(status_code=404, detail="Doctor not found")
        
        patient.assigned_doctor_id = doctor_id
        await db.commit()
        
        return {"message": f"Patient assigned to {doctor.full_name}"}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("assign_patient_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to assign patient")