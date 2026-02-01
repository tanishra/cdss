"""
LLM Service Module - Following SOLID Principles
Single Responsibility: Handle LLM interactions only
Dependency Inversion: Depends on abstractions (can swap LLM providers)
"""
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI
import json
import time
import openai
from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.schemas import SymptomInput, VitalSigns

logger = get_logger(__name__)


class LLMServiceError(Exception):
    """Custom exception for LLM service errors."""
    pass


class BaseLLMProvider:
    """
    Abstract base for LLM providers - Open/Closed Principle
    Can extend with different providers without modifying existing code
    """
    
    async def generate_differential_diagnosis(
        self, clinical_context: str, correlation_id: str
    ) -> Dict[str, Any]:
        """Generate diagnosis - to be implemented by subclasses."""
        raise NotImplementedError


class OpenAILLMProvider(BaseLLMProvider):
    """
    OpenAI AI Provider - Liskov Substitution Principle
    Can substitute any BaseLLMProvider
    """
    
    def __init__(self):
        if not settings.OPENAI_API_KEY:
            logger.warning("anthropic_api_key_missing")
            self.client = None
        else:
            self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    
    async def generate_differential_diagnosis(
        self, clinical_context: str, correlation_id: str
    ) -> Dict[str, Any]:
        """Generate differential diagnosis using OpenAI."""
        if not self.client:
            raise LLMServiceError("Anthropic API key not configured")
        
        start_time = time.time()
        
        try:
            prompt = self._create_diagnosis_prompt(clinical_context)
            
            logger.info(
                "llm_request_start",
                correlation_id=correlation_id,
                model=settings.OPENAI_MODEL,
            )
            
            response = await self.client.responses.create(
                model=settings.OPENAI_MODEL,
                temperature=settings.OPENAI_TEMPERATURE,
                input=[{"role": "user", "content": prompt}]
            )
            
            content = response.output_text
            result = self._parse_response(content)
            
            result["metadata"] = {
                "model": settings.OPENAI_MODEL,
                "tokens_used": response.usage.total_tokens,
                "processing_time_ms": (time.time() - start_time) * 1000,
            }
            
            logger.info(
                "llm_request_complete",
                correlation_id=correlation_id,
                tokens_used=result["metadata"]["tokens_used"],
                processing_time_ms=result["metadata"]["processing_time_ms"],
            )
            
            return result
            
        except openai.APIError as e:
            logger.error("llm_api_error", correlation_id=correlation_id, error=str(e))
            raise LLMServiceError(f"OpenAI API error: {str(e)}") from e
        except Exception as e:
            logger.error("llm_unexpected_error", correlation_id=correlation_id, error=str(e))
            raise LLMServiceError(f"Unexpected error: {str(e)}") from e
    
    def _create_diagnosis_prompt(self, clinical_context: str) -> str:
        """Create structured prompt for diagnosis."""
        return f"""{clinical_context}

## Task
As an experienced physician, provide a differential diagnosis for this patient. Generate the top 5 most likely diagnoses.

## Response Format
Respond ONLY with valid JSON:

{{
  "differential_diagnoses": [
    {{
      "rank": 1,
      "diagnosis": "Condition name",
      "icd10_code": "ICD-10 code",
      "confidence": 0.75,
      "reasoning": "Detailed clinical reasoning",
      "supporting_evidence": ["Evidence 1", "Evidence 2"],
      "contradicting_factors": ["Factor 1"]
    }}
  ],
  "clinical_reasoning": "Overall clinical thought process",
  "missing_information": ["Test or information needed"],
  "red_flags": ["Urgent warning signs"],
  "recommended_tests": ["Test 1", "Test 2"],
  "recommended_treatments": ["Treatment 1"],
  "follow_up_instructions": "Follow-up guidance"
}}

## Requirements
1. EXACTLY 5 differential diagnoses
2. Confidence scores 0-1
3. Specific ICD-10 codes
4. Evidence-based reasoning
5. Consider patient demographics
6. Flag urgent conditions

Respond with JSON only, no markdown."""
    
    def _parse_response(self, content: str) -> Dict[str, Any]:
        """Parse and validate LLM response."""
        try:
            # Clean markdown if present
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            result = json.loads(content)
            
            # Validate structure
            if "differential_diagnoses" not in result:
                raise ValueError("Missing differential_diagnoses")
            if "clinical_reasoning" not in result:
                raise ValueError("Missing clinical_reasoning")
            
            # Validate diagnoses
            if not isinstance(result["differential_diagnoses"], list):
                raise ValueError("differential_diagnoses must be a list")
            
            for dx in result["differential_diagnoses"]:
                required = ["diagnosis", "confidence", "reasoning", "rank"]
                for field in required:
                    if field not in dx:
                        raise ValueError(f"Missing field: {field}")
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error("llm_response_parse_error", error=str(e))
            raise LLMServiceError(f"Failed to parse response: {str(e)}") from e
        except ValueError as e:
            logger.error("llm_response_validation_error", error=str(e))
            raise LLMServiceError(f"Invalid response structure: {str(e)}") from e


class LLMService:
    """
    LLM Service - Dependency Inversion Principle
    Depends on BaseLLMProvider abstraction, not concrete implementation
    """
    
    def __init__(self, provider: Optional[BaseLLMProvider] = None):
        self.provider = provider or OpenAILLMProvider()
    
    async def generate_differential_diagnosis(
        self,
        chief_complaint: str,
        symptoms: List[SymptomInput],
        patient_age: int,
        patient_gender: str,
        medical_history: Optional[Dict[str, Any]] = None,
        vital_signs: Optional[VitalSigns] = None,
        lab_results: Optional[Dict[str, Any]] = None,
        correlation_id: str = "",
    ) -> Dict[str, Any]:
        """
        Generate differential diagnosis.
        
        Single Responsibility: Orchestrates diagnosis generation
        """
        try:
            clinical_context = self._build_clinical_context(
                chief_complaint, symptoms, patient_age, patient_gender,
                medical_history, vital_signs, lab_results
            )
            
            return await self.provider.generate_differential_diagnosis(
                clinical_context, correlation_id
            )
            
        except Exception as e:
            logger.error("diagnosis_generation_error", error=str(e), correlation_id=correlation_id)
            raise
    
    def _build_clinical_context(
        self,
        chief_complaint: str,
        symptoms: List[SymptomInput],
        patient_age: int,
        patient_gender: str,
        medical_history: Optional[Dict[str, Any]],
        vital_signs: Optional[VitalSigns],
        lab_results: Optional[Dict[str, Any]],
    ) -> str:
        """Build comprehensive clinical context string."""
        context = f"""## Patient Demographics
- Age: {patient_age} years
- Gender: {patient_gender}

## Chief Complaint
{chief_complaint}

## Present Symptoms"""
        
        for symptom in symptoms:
            context += f"\n- {symptom.name}"
            if symptom.severity:
                context += f" (Severity: {symptom.severity})"
            if symptom.duration:
                context += f" (Duration: {symptom.duration})"
            if symptom.notes:
                context += f" - {symptom.notes}"
        
        if vital_signs:
            context += "\n\n## Vital Signs"
            if vital_signs.temperature:
                context += f"\n- Temperature: {vital_signs.temperature}°C"
            if vital_signs.blood_pressure_systolic and vital_signs.blood_pressure_diastolic:
                context += f"\n- Blood Pressure: {vital_signs.blood_pressure_systolic}/{vital_signs.blood_pressure_diastolic} mmHg"
            if vital_signs.heart_rate:
                context += f"\n- Heart Rate: {vital_signs.heart_rate} BPM"
            if vital_signs.respiratory_rate:
                context += f"\n- Respiratory Rate: {vital_signs.respiratory_rate} breaths/min"
            if vital_signs.oxygen_saturation:
                context += f"\n- Oxygen Saturation: {vital_signs.oxygen_saturation}%"
        
        if medical_history:
            if medical_history.get("chronic_conditions"):
                context += f"\n\n## Chronic Conditions\n{', '.join(medical_history['chronic_conditions'])}"
            if medical_history.get("allergies"):
                context += f"\n\n## Allergies\n{', '.join(medical_history['allergies'])}"
            if medical_history.get("medications"):
                context += "\n\n## Current Medications"
                for med in medical_history["medications"]:
                    context += f"\n- {med.get('name', 'Unknown')}"
        
        if lab_results:
            context += f"\n\n## Laboratory Results\n{json.dumps(lab_results, indent=2)}"
        
        return context


# Global instance - Singleton pattern
llm_service = LLMService()