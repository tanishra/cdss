"""
AI Symptom Checker API Routes
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from app.core.database import get_db
from app.api.dependencies import get_current_doctor
from app.models.models import Doctor
from app.core.logging import get_logger
from app.services.rag_service import rag_service

logger = get_logger(__name__)
router = APIRouter()


class SymptomInput(BaseModel):
    symptom: str


class SymptomCheckRequest(BaseModel):
    symptoms: List[str]
    age: Optional[int] = None
    gender: Optional[str] = None
    duration: Optional[str] = None
    severity: Optional[str] = None


class FollowUpQuestion(BaseModel):
    question: str
    options: List[str]
    category: str  # vital_signs, history, lifestyle, etc.


def get_correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", "")


@router.post("/analyze")
async def analyze_symptoms(
    data: SymptomCheckRequest,
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
    request: Request = None,
):
    """Analyze symptoms and provide preliminary diagnosis."""
    correlation_id = get_correlation_id(request)
    
    try:
        # Build symptom context
        symptom_text = ", ".join(data.symptoms)
        
        context_parts = [f"Patient presents with: {symptom_text}"]
        
        if data.age:
            context_parts.append(f"Age: {data.age}")
        if data.gender:
            context_parts.append(f"Gender: {data.gender}")
        if data.duration:
            context_parts.append(f"Duration: {data.duration}")
        if data.severity:
            context_parts.append(f"Severity: {data.severity}")
        
        full_context = ". ".join(context_parts)
        
        # Use RAG service to get diagnosis
        prompt = f"""Based on the following symptoms, provide a differential diagnosis with top 5 possible conditions.

{full_context}

Provide:
1. Top 5 differential diagnoses with confidence scores
2. Key distinguishing features for each
3. Recommended immediate actions
4. Red flags that require immediate medical attention

Format as JSON with: diagnoses (array with diagnosis, confidence, reasoning), immediate_actions (array), red_flags (array)"""

        # Get RAG response
        rag_response = await rag_service.get_diagnosis_with_citations(
            query=full_context,
            prompt=prompt,
            doctor_id=current_doctor.id,
        )
        
        # Parse response
        import json
        import re
        
        # Extract JSON from response
        json_match = re.search(r'\{.*\}', rag_response['response'], re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            # Fallback structure
            result = {
                "diagnoses": [],
                "immediate_actions": ["Consult with a healthcare provider"],
                "red_flags": []
            }
        
        # Generate follow-up questions
        follow_up_questions = generate_follow_up_questions(data.symptoms, result.get('diagnoses', []))
        
        logger.info(
            "symptom_analysis_completed",
            symptom_count=len(data.symptoms),
            diagnoses_count=len(result.get('diagnoses', [])),
            correlation_id=correlation_id,
        )
        
        return {
            "analysis": result,
            "follow_up_questions": follow_up_questions,
            "citations": rag_response.get('citations', []),
            "confidence_level": calculate_confidence(result.get('diagnoses', [])),
            "disclaimer": "This is a preliminary analysis. Please consult a healthcare provider for proper diagnosis and treatment.",
        }
        
    except Exception as e:
        logger.error("symptom_analysis_error", error=str(e), correlation_id=correlation_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to analyze symptoms"
        )


@router.post("/guided-questions")
async def get_guided_questions(
    data: SymptomInput,
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
):
    """Get guided questions based on initial symptom."""
    try:
        questions = generate_initial_questions(data.symptom)
        return {"questions": questions}
        
    except Exception as e:
        logger.error("guided_questions_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to generate questions")


def generate_initial_questions(symptom: str) -> List[FollowUpQuestion]:
    """Generate initial guided questions based on symptom."""
    
    # Common questions for any symptom
    base_questions = [
        FollowUpQuestion(
            question="How long have you been experiencing this symptom?",
            options=["Less than 24 hours", "1-3 days", "4-7 days", "More than a week", "More than a month"],
            category="duration"
        ),
        FollowUpQuestion(
            question="How severe is the symptom?",
            options=["Mild (doesn't interfere with daily activities)", 
                    "Moderate (some interference with activities)", 
                    "Severe (significant interference)", 
                    "Very severe (unable to perform normal activities)"],
            category="severity"
        ),
        FollowUpQuestion(
            question="Is the symptom constant or does it come and go?",
            options=["Constant", "Comes and goes", "Only at certain times", "Getting worse", "Getting better"],
            category="pattern"
        ),
    ]
    
    # Symptom-specific questions
    symptom_lower = symptom.lower()
    
    if any(word in symptom_lower for word in ['pain', 'ache', 'hurt']):
        base_questions.append(
            FollowUpQuestion(
                question="What does the pain feel like?",
                options=["Sharp/stabbing", "Dull/aching", "Burning", "Throbbing", "Cramping"],
                category="quality"
            )
        )
    
    if any(word in symptom_lower for word in ['fever', 'temperature', 'hot']):
        base_questions.append(
            FollowUpQuestion(
                question="Have you measured your temperature?",
                options=["Yes, below 100°F (37.8°C)", 
                        "Yes, 100-102°F (37.8-38.9°C)", 
                        "Yes, above 102°F (38.9°C)", 
                        "No, but feel hot"],
                category="vital_signs"
            )
        )
    
    if any(word in symptom_lower for word in ['cough', 'breathing', 'shortness']):
        base_questions.extend([
            FollowUpQuestion(
                question="Do you have any difficulty breathing?",
                options=["No difficulty", "Mild difficulty", "Moderate difficulty", "Severe difficulty"],
                category="severity"
            ),
            FollowUpQuestion(
                question="Are you coughing up anything?",
                options=["No", "Clear mucus", "Yellow/green mucus", "Blood"],
                category="associated_symptoms"
            ),
        ])
    
    if any(word in symptom_lower for word in ['headache', 'head']):
        base_questions.extend([
            FollowUpQuestion(
                question="Where is the headache located?",
                options=["Front (forehead)", "Sides (temples)", "Back of head", "Top of head", "All over"],
                category="location"
            ),
            FollowUpQuestion(
                question="Do you have any visual changes?",
                options=["No", "Blurred vision", "Seeing spots/auras", "Light sensitivity"],
                category="associated_symptoms"
            ),
        ])
    
    if any(word in symptom_lower for word in ['stomach', 'abdominal', 'belly', 'nausea', 'vomit']):
        base_questions.extend([
            FollowUpQuestion(
                question="Where in your abdomen is the discomfort?",
                options=["Upper abdomen", "Lower abdomen", "Right side", "Left side", "All over"],
                category="location"
            ),
            FollowUpQuestion(
                question="Have you had any changes in bowel movements?",
                options=["No changes", "Diarrhea", "Constipation", "Blood in stool"],
                category="associated_symptoms"
            ),
        ])
    
    return base_questions


def generate_follow_up_questions(symptoms: List[str], diagnoses: List[dict]) -> List[FollowUpQuestion]:
    """Generate follow-up questions based on symptoms and preliminary diagnoses."""
    
    questions = []
    
    # Medical history questions
    questions.append(
        FollowUpQuestion(
            question="Do you have any pre-existing medical conditions?",
            options=["None", "Diabetes", "High blood pressure", "Heart disease", "Asthma", "Other"],
            category="medical_history"
        )
    )
    
    # Medication questions
    questions.append(
        FollowUpQuestion(
            question="Are you currently taking any medications?",
            options=["No medications", "Prescription medications", "Over-the-counter medications", "Herbal supplements"],
            category="medications"
        )
    )
    
    # Lifestyle questions
    questions.extend([
        FollowUpQuestion(
            question="Have you traveled recently?",
            options=["No", "Within country", "International travel"],
            category="lifestyle"
        ),
        FollowUpQuestion(
            question="Have you been exposed to anyone with similar symptoms?",
            options=["No known exposure", "Yes, at home", "Yes, at work/school", "Yes, in public"],
            category="exposure"
        ),
    ])
    
    return questions


def calculate_confidence(diagnoses: List[dict]) -> str:
    """Calculate overall confidence level."""
    if not diagnoses:
        return "Low"
    
    top_confidence = diagnoses[0].get('confidence', 0) if diagnoses else 0
    
    if top_confidence >= 0.8:
        return "High"
    elif top_confidence >= 0.6:
        return "Medium"
    else:
        return "Low"


@router.get("/common-symptoms")
async def get_common_symptoms(
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
):
    """Get list of common symptoms for quick selection."""
    
    common_symptoms = {
        "general": [
            "Fever", "Fatigue", "Weight loss", "Weight gain", "Night sweats", "Chills"
        ],
        "head_neck": [
            "Headache", "Dizziness", "Sore throat", "Ear pain", "Vision changes", "Hearing loss"
        ],
        "respiratory": [
            "Cough", "Shortness of breath", "Wheezing", "Chest pain", "Runny nose", "Congestion"
        ],
        "cardiovascular": [
            "Chest pain", "Palpitations", "Rapid heartbeat", "Leg swelling", "Fainting"
        ],
        "gastrointestinal": [
            "Nausea", "Vomiting", "Diarrhea", "Constipation", "Abdominal pain", "Loss of appetite"
        ],
        "musculoskeletal": [
            "Joint pain", "Muscle aches", "Back pain", "Neck pain", "Stiffness", "Swelling"
        ],
        "neurological": [
            "Numbness", "Tingling", "Weakness", "Memory problems", "Confusion", "Seizures"
        ],
        "skin": [
            "Rash", "Itching", "Bruising", "Skin changes", "Wounds", "Hair loss"
        ],
        "urinary": [
            "Painful urination", "Frequent urination", "Blood in urine", "Difficulty urinating"
        ],
    }
    
    return common_symptoms