"""
Seed database with default roles and permissions
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.models import Role
from app.core.logging import get_logger

logger = get_logger(__name__)


async def seed_roles(db: AsyncSession):
    """Create default roles."""
    try:
        # Check if roles exist
        result = await db.execute(select(Role))
        existing_roles = result.scalars().all()
        
        if len(existing_roles) > 0:
            logger.info("Roles already seeded")
            return
        
        roles = [
            {
                "name": "admin",
                "description": "Full system access - can manage organization, doctors, and all data",
                "permissions": {
                    "can_manage_organization": True,
                    "can_manage_doctors": True,
                    "can_manage_patients": True,
                    "can_manage_departments": True,
                    "can_view_all_diagnoses": True,
                    "can_edit_all_diagnoses": True,
                    "can_delete_diagnoses": True,
                    "can_view_analytics": True,
                    "can_export_data": True,
                }
            },
            {
                "name": "doctor",
                "description": "Standard doctor access - can manage own patients and diagnoses",
                "permissions": {
                    "can_manage_organization": False,
                    "can_manage_doctors": False,
                    "can_manage_patients": True,
                    "can_manage_departments": False,
                    "can_view_all_diagnoses": False,
                    "can_edit_all_diagnoses": False,
                    "can_delete_diagnoses": False,
                    "can_view_analytics": True,
                    "can_export_data": True,
                }
            },
            {
                "name": "nurse",
                "description": "Nurse access - can view and add clinical notes",
                "permissions": {
                    "can_manage_organization": False,
                    "can_manage_doctors": False,
                    "can_manage_patients": False,
                    "can_manage_departments": False,
                    "can_view_all_diagnoses": True,
                    "can_edit_all_diagnoses": False,
                    "can_delete_diagnoses": False,
                    "can_view_analytics": False,
                    "can_export_data": False,
                }
            },
            {
                "name": "receptionist",
                "description": "Reception access - can manage appointments and patient registration",
                "permissions": {
                    "can_manage_organization": False,
                    "can_manage_doctors": False,
                    "can_manage_patients": True,
                    "can_manage_departments": False,
                    "can_view_all_diagnoses": False,
                    "can_edit_all_diagnoses": False,
                    "can_delete_diagnoses": False,
                    "can_view_analytics": False,
                    "can_export_data": False,
                }
            },
        ]
        
        for role_data in roles:
            role = Role(**role_data)
            db.add(role)
        
        await db.commit()
        logger.info("Roles seeded successfully")
        
    except Exception as e:
        await db.rollback()
        logger.error("Failed to seed roles", error=str(e))
        raise