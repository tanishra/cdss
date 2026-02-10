"""
LLM Service Module - GPT-4o-mini with RAG
"""
from typing import List, Dict, Any, Optional
import openai
from openai import AsyncOpenAI
import json
import time

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.schemas import SymptomInput, VitalSigns

logger = get_logger(__name__)


class LLMServiceError(Exception):
    """Custom exception for LLM service errors."""
    pass


class LLMService:
    """
    LLM Service for GPT-4o-mini with RAG support.
    """
    
    def __init__(self):
        if not settings.OPENAI_API_KEY:
            logger.warning("openai_api_key_missing", message="LLM features will not work")
            self.client = None
        else:
            self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    
    async def generate_differential_diagnosis(
        self,
        chief_complaint: str,
        symptoms: List[SymptomInput],
        patient_age: int,
        patient_gender: str,
        medical_history: Optional[Dict[str, Any]] = None,
        vital_signs: Optional[VitalSigns] = None,
        lab_results: Optional[Dict[str, Any]] = None,
        evidence: Optional[Dict[str, Any]] = None,  # NEW: RAG evidence
        correlation_id: str = "",
    ) -> Dict[str, Any]:
        """
        Generate differential diagnosis using GPT-4o-mini with optional evidence.
        """
        if not self.client:
            raise LLMServiceError("OpenAI API key not configured")
        
        start_time = time.time()
        
        try:
            # Build clinical context
            clinical_context = self._build_clinical_context(
                chief_complaint=chief_complaint,
                symptoms=symptoms,
                patient_age=patient_age,
                patient_gender=patient_gender,
                medical_history=medical_history,
                vital_signs=vital_signs,
                lab_results=lab_results,
            )
            
            # Add evidence if available (RAG)
            evidence_context = ""
            if evidence and evidence.get("evidence"):
                evidence_context = self._format_evidence_for_prompt(evidence["evidence"])
            
            # Create prompt
            prompt = self._create_diagnosis_prompt(clinical_context, evidence_context)
            
            logger.info(
                "llm_request_start",
                correlation_id=correlation_id,
                model=settings.OPENAI_MODEL,
                has_evidence=bool(evidence_context),
            )
            
            # Call GPT-4o-mini API
            response = await self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an experienced physician providing evidence-based differential diagnoses."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=settings.OPENAI_TEMPERATURE,
                response_format={"type": "json_object"}  # Force JSON response
            )
            
            # Parse response
            content = response.choices[0].message.content
            result = self._parse_llm_response(content)
            
            # Add metadata
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
                diagnoses_count=len(result.get("differential_diagnoses", [])),
            )
            
            return result
            
        except openai.APIError as e:
            logger.error(
                "llm_api_error",
                correlation_id=correlation_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise LLMServiceError(f"OpenAI API error: {str(e)}") from e
        except Exception as e:
            logger.error(
                "llm_unexpected_error",
                correlation_id=correlation_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise LLMServiceError(f"Unexpected error: {str(e)}") from e
    
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
        """Build clinical context string."""
        context = f"""## Patient Information
- Age: {patient_age} years
- Gender: {patient_gender}

## Chief Complaint
{chief_complaint}

## Symptoms"""
        
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
    
    def _format_evidence_for_prompt(self, evidence: List[Dict[str, Any]]) -> str:
        """Format RAG evidence for LLM prompt."""
        if not evidence:
            return ""
        
        formatted = "\n\n## Medical Literature Evidence\n\n"
        formatted += "The following peer-reviewed studies and clinical guidelines are relevant:\n\n"
        
        for i, item in enumerate(evidence[:5], 1):  # Top 5 evidence
            evidence_type = item.get("evidence_type", "research").upper()
            title = item.get("title", "Unknown")
            authors = item.get("authors", "Unknown")
            source = item.get("source", "")
            
            formatted += f"**[{i}] {evidence_type}**\n"
            formatted += f"Title: {title}\n"
            formatted += f"Authors: {authors}\n"
            
            # Add abstract/summary
            abstract = item.get("abstract", item.get("summary", ""))
            if abstract:
                if len(abstract) > 300:
                    abstract = abstract[:300] + "..."
                formatted += f"Summary: {abstract}\n"
            
            formatted += f"Source: {source}\n\n"
        
        formatted += "Please use this evidence to support your differential diagnoses.\n"
        
        return formatted
    
    def _create_diagnosis_prompt(self, clinical_context: str, evidence_context: str) -> str:
        """Create comprehensive prompt with optional evidence."""
        prompt = f"""{clinical_context}

{evidence_context}

## Task
Provide evidence-based differential diagnoses for this patient. Generate the top 5 most likely diagnoses.

## Response Format
Return ONLY valid JSON (no markdown, no explanations):

{{
  "differential_diagnoses": [
    {{
      "rank": 1,
      "diagnosis": "Condition name",
      "icd10_code": "ICD-10 code",
      "confidence": 0.75,
      "reasoning": "Detailed clinical reasoning with evidence citations if available",
      "supporting_evidence": ["Evidence point 1", "Evidence point 2", "Evidence point 3"],
      "contradicting_factors": ["Factor 1 that makes this less likely"]
    }}
  ],
  "clinical_reasoning": "Overall clinical thought process",
  "missing_information": ["Test or information that would help"],
  "red_flags": ["Urgent warning signs"],
  "recommended_tests": ["Diagnostic test 1", "Diagnostic test 2"],
  "recommended_treatments": ["Treatment approach 1", "Treatment approach 2"],
  "follow_up_instructions": "When and why patient should follow up"
}}

## Requirements
1. Provide EXACTLY 5 differential diagnoses ranked by likelihood
2. Confidence scores between 0-1 (e.g., 0.75 = 75% confident)
3. Specific ICD-10 codes
4. If medical literature was provided, reference it in your reasoning
5. Consider patient age and gender
6. Flag any urgent/dangerous symptoms
7. Be specific with evidence-based recommendations

Return only the JSON object."""
        
        return prompt
    
    def _parse_llm_response(self, content: str) -> Dict[str, Any]:
        """Parse and validate LLM response."""
        try:
            # Clean response
            content = content.strip()
            
            # Remove markdown if present
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            
            content = content.strip()
            
            # Parse JSON
            result = json.loads(content)
            
            # Validate required fields
            if "differential_diagnoses" not in result:
                raise ValueError("Missing differential_diagnoses")
            if "clinical_reasoning" not in result:
                raise ValueError("Missing clinical_reasoning")
            
            # Validate diagnoses structure
            if not isinstance(result["differential_diagnoses"], list):
                raise ValueError("differential_diagnoses must be a list")
            
            for dx in result["differential_diagnoses"]:
                required = ["diagnosis", "confidence", "reasoning", "rank"]
                for field in required:
                    if field not in dx:
                        raise ValueError(f"Missing field in diagnosis: {field}")
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error("llm_response_parse_error", error=str(e), content_preview=content[:200])
            raise LLMServiceError(f"Failed to parse LLM response: {str(e)}") from e
        except ValueError as e:
            logger.error("llm_response_validation_error", error=str(e))
            raise LLMServiceError(f"Invalid LLM response structure: {str(e)}") from e


# Global instance
llm_service = LLMService()