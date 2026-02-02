"""
Pydantic Schemas Module - Following SOLID Principles
Interface Segregation: Separate schemas for different use cases
"""
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field, validator
from enum import Enum


# ============================================================================
# ENUMS - Open/Closed Principle: Easy to extend
# ============================================================================

class Gender(str, Enum):
    """Gender enumeration."""
    MALE = "Male"
    FEMALE = "Female"
    OTHER = "Other"


class SmokingStatus(str, Enum):
    """Smoking status enumeration."""
    NEVER = "Never"
    FORMER = "Former"
    CURRENT = "Current"


class AlcoholConsumption(str, Enum):
    """Alcohol consumption enumeration."""
    NONE = "None"
    OCCASIONAL = "Occasional"
    REGULAR = "Regular"


class Severity(str, Enum):
    """Symptom severity enumeration."""
    MILD = "Mild"
    MODERATE = "Moderate"
    SEVERE = "Severe"


class DiagnosisStatus(str, Enum):
    """Diagnosis status enumeration."""
    ACTIVE = "active"
    REVIEWED = "reviewed"
    ARCHIVED = "archived"


# ============================================================================
# AUTHENTICATION SCHEMAS - Single Responsibility Principle
# ============================================================================

class DoctorRegister(BaseModel):
    """Doctor registration request schema."""
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=2, max_length=200)
    specialization: Optional[str] = None
    license_number: Optional[str] = None
    phone: Optional[str] = None
    
    @validator('password')
    def validate_password(cls, v):
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain digit')
        return v


class DoctorLogin(BaseModel):
    """Doctor login request schema."""
    email: EmailStr
    password: str


class Token(BaseModel):
    """JWT token response schema."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class DoctorResponse(BaseModel):
    """Doctor information response schema."""
    id: str
    email: str
    full_name: str
    specialization: Optional[str]
    license_number: Optional[str]
    phone: Optional[str]
    is_active: bool
    is_verified: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============================================================================
# PATIENT SCHEMAS - Interface Segregation Principle
# ============================================================================

class PatientBase(BaseModel):
    """Base patient schema - DRY principle."""
    mrn: str = Field(..., description="Medical Record Number")
    full_name: str = Field(..., min_length=2, max_length=200)
    date_of_birth: date
    gender: Gender
    blood_group: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None


class PatientCreate(PatientBase):
    """Patient creation schema."""
    allergies: Optional[List[str]] = None
    chronic_conditions: Optional[List[str]] = None
    medications: Optional[List[Dict[str, str]]] = None
    family_history: Optional[Dict[str, Any]] = None
    surgical_history: Optional[List[Dict[str, str]]] = None
    smoking_status: Optional[SmokingStatus] = None
    alcohol_consumption: Optional[AlcoholConsumption] = None
    notes: Optional[str] = None


class PatientUpdate(BaseModel):
    """Patient update schema - Only updatable fields."""
    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    allergies: Optional[List[str]] = None
    chronic_conditions: Optional[List[str]] = None
    medications: Optional[List[Dict[str, str]]] = None
    smoking_status: Optional[SmokingStatus] = None
    alcohol_consumption: Optional[AlcoholConsumption] = None
    notes: Optional[str] = None


class PatientResponse(PatientBase):
    """Patient response schema."""
    id: str
    allergies: Optional[List[str]]
    chronic_conditions: Optional[List[str]]
    medications: Optional[List[Dict[str, str]]]
    smoking_status: Optional[str]
    alcohol_consumption: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True


# ============================================================================
# DIAGNOSIS SCHEMAS - Single Responsibility Principle
# ============================================================================

class VitalSigns(BaseModel):
    """Vital signs schema - Separate concern."""
    temperature: Optional[float] = Field(None, ge=35.0, le=42.0)
    blood_pressure_systolic: Optional[int] = Field(None, ge=60, le=250)
    blood_pressure_diastolic: Optional[int] = Field(None, ge=40, le=150)
    heart_rate: Optional[int] = Field(None, ge=40, le=200)
    respiratory_rate: Optional[int] = Field(None, ge=8, le=40)
    oxygen_saturation: Optional[float] = Field(None, ge=70.0, le=100.0)


class SymptomInput(BaseModel):
    """Individual symptom schema."""
    name: str = Field(..., description="Symptom name")
    severity: Optional[Severity] = None
    duration: Optional[str] = Field(None, description="e.g., '3 days'")
    notes: Optional[str] = None


class DiagnosisRequest(BaseModel):
    """Diagnosis analysis request schema."""
    patient_id: str
    chief_complaint: str = Field(..., min_length=5, max_length=500)
    symptoms: List[SymptomInput] = Field(..., min_items=1)
    symptom_duration: Optional[str] = None
    symptom_severity: Optional[Severity] = None
    vital_signs: Optional[VitalSigns] = None
    lab_results: Optional[Dict[str, Any]] = None
    imaging_findings: Optional[Dict[str, Any]] = None
    
    @validator('symptoms')
    def validate_symptoms(cls, v):
        """Validate symptoms list."""
        if not v:
            raise ValueError('At least one symptom is required')
        return v
    
class CitationBase(BaseModel):
    """Base citation schema."""
    pubmed_id: Optional[str] = None
    title: str
    authors: Optional[str] = None
    journal: Optional[str] = None
    publication_year: Optional[int] = None
    doi: Optional[str] = None
    citation_text: str
    relevance_score: float
    evidence_type: str  # "research", "guideline", "review"
    abstract: Optional[str] = None
    url: Optional[str] = None


class CitationResponse(CitationBase):
    """Citation response schema."""
    id: str
    diagnosis_id: str
    diagnosis_name: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class DifferentialDiagnosisWithEvidence(BaseModel):
    """Enhanced differential diagnosis with evidence."""
    diagnosis: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    icd10_code: str
    reasoning: str
    supporting_evidence: List[str]
    contradicting_factors: Optional[List[str]] = None
    rank: int
    citations: List[CitationBase] = []
    evidence_quality: str = "low"  # "low", "moderate", "high"


class DiagnosisResponseWithEvidence(BaseModel):
    """Enhanced diagnosis response with RAG."""
    id: str
    patient_id: str
    correlation_id: str
    chief_complaint: str
    symptoms: List[Dict[str, Any]]
    differential_diagnoses: List[DifferentialDiagnosisWithEvidence]
    clinical_reasoning: str
    missing_information: Optional[List[str]]
    red_flags: Optional[List[str]]
    recommended_tests: Optional[List[str]]
    recommended_treatments: Optional[List[str]]
    follow_up_instructions: Optional[str]
    evidence_used: Optional[List[Dict[str, Any]]]
    guidelines_applied: Optional[List[str]]
    citation_count: int
    rag_enabled: bool
    processing_time_ms: float
    confidence_level: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class DiagnosisFeedback(BaseModel):
    """Doctor feedback schema - Dependency Inversion."""
    correct_diagnosis: str
    was_in_top_5: bool
    actual_rank: Optional[int] = Field(None, ge=1, le=5)
    feedback_notes: Optional[str] = None

class DoctorFeedbackCreate(BaseModel):
    """Doctor feedback creation schema."""
    diagnosis_id: str
    correct_diagnosis: str
    was_in_top_5: bool
    actual_rank: Optional[int] = Field(None, ge=1, le=5)
    missing_symptoms: Optional[List[str]] = None
    incorrect_symptoms: Optional[List[str]] = None
    missing_tests: Optional[List[str]] = None
    accuracy_rating: Optional[int] = Field(None, ge=1, le=5)
    reasoning_quality: Optional[int] = Field(None, ge=1, le=5)
    recommendations_quality: Optional[int] = Field(None, ge=1, le=5)
    overall_satisfaction: Optional[int] = Field(None, ge=1, le=5)
    feedback_notes: Optional[str] = None
    would_use_again: Optional[bool] = None
    treatment_given: Optional[str] = None
    patient_outcome: Optional[str] = None  # "improved", "stable", "worsened"


class DoctorFeedbackResponse(DoctorFeedbackCreate):
    """Doctor feedback response schema."""
    id: str
    doctor_id: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class FeedbackStats(BaseModel):
    """Feedback statistics schema."""
    total_feedbacks: int
    average_accuracy: float
    top_5_accuracy: float  
    average_satisfaction: float
    would_use_again_percentage: float
    common_issues: List[Dict[str, Any]]


class RAGConfig(BaseModel):
    """RAG configuration for diagnosis."""
    enable_rag: bool = True
    max_pubmed_results: int = 10
    min_evidence_score: float = 0.7
    include_guidelines: bool = True
    evidence_types: List[str] = ["research", "guideline", "review"]

# ============================================================================
# COMMON SCHEMAS
# ============================================================================

class HealthCheck(BaseModel):
    """Health check response schema."""
    status: str
    timestamp: datetime
    version: str
    database: str
    redis: str


class ErrorResponse(BaseModel):
    """Error response schema."""
    error: str
    detail: Optional[str] = None
    correlation_id: Optional[str] = None
    timestamp: datetime


class SuccessResponse(BaseModel):
    """Generic success response schema."""
    message: str
    data: Optional[Dict[str, Any]] = None
    correlation_id: Optional[str] = None