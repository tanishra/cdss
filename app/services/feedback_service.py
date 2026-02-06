"""
Feedback Service - Handle doctor feedback on diagnoses
"""
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import uuid

from app.models.models import DoctorFeedback, Diagnosis
from app.schemas.schemas import DoctorFeedbackCreate
from app.core.logging import get_logger, audit_logger

logger = get_logger(__name__)


class FeedbackServiceError(Exception):
    """Feedback service exception."""
    pass


class FeedbackService:
    """Service for managing doctor feedback."""
    
    async def create_feedback(
        self,
        db: AsyncSession,
        feedback_data: DoctorFeedbackCreate,
        doctor_id: str,
        correlation_id: str
    ) -> DoctorFeedback:
        """
        Create doctor feedback for a diagnosis.
        
        Args:
            db: Database session
            feedback_data: Feedback data
            doctor_id: Doctor providing feedback
            correlation_id: Request tracking ID
            
        Returns:
            Created feedback record
        """
        try:
            # Validate diagnosis exists and belongs to doctor
            diagnosis = await self._get_diagnosis(
                db, feedback_data.diagnosis_id, doctor_id
            )
            
            if not diagnosis:
                raise FeedbackServiceError(
                    f"Diagnosis not found: {feedback_data.diagnosis_id}"
                )
            
            # Create feedback record
            feedback = DoctorFeedback(
                id=str(uuid.uuid4()),
                diagnosis_id=feedback_data.diagnosis_id,
                doctor_id=doctor_id,
                correct_diagnosis=feedback_data.correct_diagnosis,
                was_in_top_5=feedback_data.was_in_top_5,
                actual_rank=feedback_data.actual_rank,
                missing_symptoms=feedback_data.missing_symptoms,
                incorrect_symptoms=feedback_data.incorrect_symptoms,
                missing_tests=feedback_data.missing_tests,
                accuracy_rating=feedback_data.accuracy_rating,
                reasoning_quality=feedback_data.reasoning_quality,
                recommendations_quality=feedback_data.recommendations_quality,
                overall_satisfaction=feedback_data.overall_satisfaction,
                feedback_notes=feedback_data.feedback_notes,
                would_use_again=feedback_data.would_use_again,
                treatment_given=feedback_data.treatment_given,
                patient_outcome=feedback_data.patient_outcome,
            )
            
            db.add(feedback)
            
            # Update diagnosis with feedback summary
            diagnosis.doctor_feedback = {
                "correct_diagnosis": feedback_data.correct_diagnosis,
                "was_in_top_5": feedback_data.was_in_top_5,
                "actual_rank": feedback_data.actual_rank,
                "overall_satisfaction": feedback_data.overall_satisfaction,
                "feedback_date": feedback.created_at.isoformat() if feedback.created_at else None,
            }
            diagnosis.status = "reviewed"
            
            await db.commit()
            await db.refresh(feedback)
            
            # Audit log
            audit_logger.logger.info(
                "feedback_created",
                event_type="feedback",
                feedback_id=feedback.id,
                diagnosis_id=feedback_data.diagnosis_id,
                doctor_id=doctor_id,
                was_accurate=feedback_data.was_in_top_5,
                correlation_id=correlation_id,
            )
            
            logger.info(
                "feedback_created",
                feedback_id=feedback.id,
                diagnosis_id=feedback_data.diagnosis_id,
                was_in_top_5=feedback_data.was_in_top_5,
                correlation_id=correlation_id,
            )
            
            return feedback
            
        except FeedbackServiceError:
            raise
        except Exception as e:
            logger.error(
                "feedback_creation_error",
                error=str(e),
                correlation_id=correlation_id,
            )
            raise FeedbackServiceError(f"Failed to create feedback: {str(e)}") from e
    
    async def get_feedback_stats(
        self,
        db: AsyncSession,
        doctor_id: Optional[str] = None,
        correlation_id: str = ""
    ) -> Dict[str, Any]:
        """
        Get feedback statistics.
        
        Args:
            db: Database session
            doctor_id: Filter by specific doctor (optional)
            correlation_id: Request tracking ID
            
        Returns:
            Feedback statistics
        """
        try:
            # Build query
            query = select(DoctorFeedback)
            if doctor_id:
                query = query.where(DoctorFeedback.doctor_id == doctor_id)
            
            result = await db.execute(query)
            feedbacks = result.scalars().all()
            
            if not feedbacks:
                return {
                    "total_feedbacks": 0,
                    "average_accuracy": 0.0,
                    "top_5_accuracy": 0.0,
                    "average_satisfaction": 0.0,
                    "would_use_again_percentage": 0.0,
                    "common_issues": []
                }
            
            # Calculate statistics
            total = len(feedbacks)
            top_5_correct = sum(1 for f in feedbacks if f.was_in_top_5)
            
            # Average ratings
            ratings = [f.overall_satisfaction for f in feedbacks if f.overall_satisfaction]
            avg_satisfaction = sum(ratings) / len(ratings) if ratings else 0.0
            
            # Would use again
            would_use = [f.would_use_again for f in feedbacks if f.would_use_again is not None]
            would_use_pct = (sum(would_use) / len(would_use) * 100) if would_use else 0.0
            
            # Common issues
            missing_symptoms_list = []
            for f in feedbacks:
                if f.missing_symptoms:
                    missing_symptoms_list.extend(f.missing_symptoms)
            
            # Count symptom frequency
            symptom_counts = {}
            for symptom in missing_symptoms_list:
                symptom_counts[symptom] = symptom_counts.get(symptom, 0) + 1
            
            # Top 5 common issues
            common_issues = [
                {"issue": symptom, "count": count}
                for symptom, count in sorted(
                    symptom_counts.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:5]
            ]
            
            stats = {
                "total_feedbacks": total,
                "average_accuracy": top_5_correct / total if total > 0 else 0.0,
                "top_5_accuracy": (top_5_correct / total * 100) if total > 0 else 0.0,
                "average_satisfaction": avg_satisfaction,
                "would_use_again_percentage": would_use_pct,
                "common_issues": common_issues,
            }
            
            logger.info(
                "feedback_stats_generated",
                stats=stats,
                correlation_id=correlation_id,
            )
            
            return stats
            
        except Exception as e:
            logger.error(
                "feedback_stats_error",
                error=str(e),
                correlation_id=correlation_id,
            )
            raise FeedbackServiceError(f"Failed to get feedback stats: {str(e)}") from e
    
    async def _get_diagnosis(
        self, db: AsyncSession, diagnosis_id: str, doctor_id: str
    ) -> Optional[Diagnosis]:
        """Get diagnosis and verify ownership."""
        result = await db.execute(
            select(Diagnosis).where(
                Diagnosis.id == diagnosis_id,
                Diagnosis.doctor_id == doctor_id
            )
        )
        return result.scalar_one_or_none()
    
    async def get_feedback_by_diagnosis(
        self,
        db: AsyncSession,
        diagnosis_id: str,
        doctor_id: str,
        correlation_id: str = ""
    ) -> Optional[DoctorFeedback]:
        """Get feedback for specific diagnosis."""
        try:
            result = await db.execute(
                select(DoctorFeedback).where(
                    DoctorFeedback.diagnosis_id == diagnosis_id,
                    DoctorFeedback.doctor_id == doctor_id
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error("get_feedback_error", error=str(e), correlation_id=correlation_id)
            return None


# Global instance
feedback_service = FeedbackService()