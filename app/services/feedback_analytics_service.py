"""
Feedback Analytics Service - Learn from doctor feedback
"""
from typing import Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from collections import Counter

from app.models.models import DoctorFeedback, Diagnosis
from app.core.logging import get_logger

logger = get_logger(__name__)


class FeedbackAnalyticsService:
    """Analyze feedback to improve RAG and prompts."""
    
    async def get_evidence_effectiveness(
        self, db: AsyncSession
    ) -> Dict[str, float]:
        """
        Analyze which evidence sources led to correct diagnoses.
        Returns journal/source effectiveness scores.
        """
        result = await db.execute(
            select(DoctorFeedback, Diagnosis)
            .join(Diagnosis, DoctorFeedback.diagnosis_id == Diagnosis.id)
            .where(DoctorFeedback.was_in_top_5 == True)
        )
        
        correct_diagnoses = result.all()
        
        # Track which evidence sources appeared in correct diagnoses
        source_success = Counter()
        source_total = Counter()
        
        for feedback, diagnosis in correct_diagnoses:
            if diagnosis.evidence_used:
                for evidence in diagnosis.evidence_used:
                    journal = evidence.get("journal", "Unknown")
                    source_total[journal] += 1
                    if feedback.actual_rank == 1:  # Top diagnosis was correct
                        source_success[journal] += 1
        
        # Calculate success rates
        effectiveness = {}
        for journal, total in source_total.items():
            if total >= 3:  # Need at least 3 samples
                effectiveness[journal] = source_success[journal] / total
        
        logger.info("evidence_effectiveness_calculated", sources=len(effectiveness))
        return effectiveness
    
    async def get_common_mistakes(
        self, db: AsyncSession, limit: int = 10
    ) -> List[Dict]:
        """Get most common diagnostic mistakes."""
        result = await db.execute(
            select(
                DoctorFeedback.correct_diagnosis,
                func.count(DoctorFeedback.id).label('count')
            )
            .where(DoctorFeedback.was_in_top_5 == False)
            .group_by(DoctorFeedback.correct_diagnosis)
            .order_by(func.count(DoctorFeedback.id).desc())
            .limit(limit)
        )
        
        mistakes = [
            {"diagnosis": row[0], "missed_count": row[1]}
            for row in result.all()
        ]
        
        return mistakes
    
    async def get_missing_symptoms_analysis(
        self, db: AsyncSession
    ) -> Dict[str, int]:
        """Analyze commonly missing symptoms."""
        result = await db.execute(select(DoctorFeedback))
        feedbacks = result.scalars().all()
        
        all_missing = []
        for feedback in feedbacks:
            if feedback.missing_symptoms:
                all_missing.extend(feedback.missing_symptoms)
        
        # Count frequency
        symptom_counts = Counter(all_missing)
        return dict(symptom_counts.most_common(20))


# Global instance
feedback_analytics_service = FeedbackAnalyticsService()