"""
Pydantic Schemas Module - Following SOLID Principles
Interface Segregation: Separate schemas for different use cases
"""
from datetime import datetime, date
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, EmailStr, Field, field_validator
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
    
    @field_validator('password')
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

# ----------------------------------------------
# Lab Results
# ----------------------------------------------

class LabResultInput(BaseModel):
    """Lab result input - either text or structured."""
    format: str = "json"  # "json" or "text"
    data: Union[Dict[str, float], str]  # JSON dict or raw text


class LabResultParsed(BaseModel):
    """Parsed lab result."""
    test: str
    value: float
    unit: str
    reference_range: Dict[str, float]
    status: str = "NORMAL"  # NORMAL, LOW, HIGH


class LabAbnormality(BaseModel):
    """Abnormal lab value."""
    test: str
    value: float
    unit: str
    status: str  # LOW or HIGH
    severity: str  # MILD, MODERATE, CRITICAL
    reference_range: str

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
    lab_results_input: Optional[LabResultInput] = None
    
    @field_validator('symptoms')
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

# Treatment Schemas
class TreatmentBase(BaseModel):
    diagnosis_id: str
    treatment_type: str
    medication_name: Optional[str] = None
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    route: Optional[str] = None
    duration: Optional[str] = None
    instructions: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class TreatmentCreate(TreatmentBase):
    pass


class TreatmentUpdate(BaseModel):
    status: Optional[str] = None
    effectiveness: Optional[str] = None
    side_effects: Optional[List[str]] = None
    adherence: Optional[str] = None
    notes: Optional[str] = None
    discontinuation_reason: Optional[str] = None
    end_date: Optional[datetime] = None


class TreatmentResponse(TreatmentBase):
    id: str
    patient_id: str
    status: str
    effectiveness: Optional[str]
    side_effects: Optional[List[str]]
    adherence: Optional[str]
    has_interactions: bool
    interaction_warnings: Optional[List[Dict[str, str]]]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Prescription Schemas
class MedicationItem(BaseModel):
    name: str
    dosage: str
    frequency: str
    route: str
    duration: str
    instructions: Optional[str] = None


class PrescriptionCreate(BaseModel):
    patient_id: str
    diagnosis_id: Optional[str] = None
    medications: List[MedicationItem]
    diagnosis_summary: Optional[str] = None
    special_instructions: Optional[str] = None
    refills_allowed: int = 0
    valid_days: int = 30


class PrescriptionResponse(BaseModel):
    id: str
    prescription_number: str
    patient_id: str
    doctor_id: str
    date_issued: datetime
    valid_until: datetime
    medications: List[Dict[str, str]]
    diagnosis_summary: Optional[str]
    special_instructions: Optional[str]
    refills_allowed: int
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True
    
# Clinical Notes
class ClinicalNoteCreate(BaseModel):
    patient_id: str
    diagnosis_id: Optional[str] = None
    title: str
    content: str
    note_type: str = "general"
    is_private: bool = False


class ClinicalNoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    note_type: Optional[str] = None
    is_private: Optional[bool] = None


class ClinicalNoteResponse(BaseModel):
    id: str
    patient_id: str
    doctor_id: str
    diagnosis_id: Optional[str]
    title: str
    content: str
    note_type: str
    is_private: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Vital Records
class VitalRecordCreate(BaseModel):
    patient_id: str
    diagnosis_id: Optional[str] = None
    temperature: Optional[float] = None
    blood_pressure_systolic: Optional[int] = None
    blood_pressure_diastolic: Optional[int] = None
    heart_rate: Optional[int] = None
    respiratory_rate: Optional[int] = None
    oxygen_saturation: Optional[float] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    blood_glucose: Optional[float] = None
    notes: Optional[str] = None
    recorded_at: Optional[datetime] = None


class VitalRecordResponse(BaseModel):
    id: str
    patient_id: str
    doctor_id: str
    diagnosis_id: Optional[str]
    temperature: Optional[float]
    blood_pressure_systolic: Optional[int]
    blood_pressure_diastolic: Optional[int]
    heart_rate: Optional[int]
    respiratory_rate: Optional[int]
    oxygen_saturation: Optional[float]
    weight: Optional[float]
    height: Optional[float]
    bmi: Optional[float]
    blood_glucose: Optional[float]
    notes: Optional[str]
    recorded_at: datetime
    created_at: datetime
    
    class Config:
        from_attributes = True


# Appointments
class AppointmentCreate(BaseModel):
    patient_id: str
    diagnosis_id: Optional[str] = None
    title: str
    appointment_type: str = "follow_up"
    scheduled_at: datetime
    duration_minutes: int = 30
    notes: Optional[str] = None


class AppointmentUpdate(BaseModel):
    title: Optional[str] = None
    appointment_type: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class AppointmentResponse(BaseModel):
    id: str
    patient_id: str
    doctor_id: str
    diagnosis_id: Optional[str]
    title: str
    appointment_type: str
    scheduled_at: datetime
    duration_minutes: int
    status: str
    notes: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


# Doctor Profile
class DoctorProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    bio: Optional[str] = None
    hospital: Optional[str] = None
    department: Optional[str] = None
    years_experience: Optional[int] = None
    specialization: Optional[str] = None


class DoctorSettingsUpdate(BaseModel):
    email_notifications: Optional[bool] = None
    appointment_reminders: Optional[bool] = None
    default_appointment_duration: Optional[int] = None


class DoctorProfileResponse(BaseModel):
    id: str
    email: str
    full_name: str
    specialization: Optional[str]
    license_number: Optional[str]
    phone: Optional[str]
    bio: Optional[str]
    hospital: Optional[str]
    department: Optional[str]
    years_experience: Optional[int]
    email_notifications: bool
    appointment_reminders: bool
    default_appointment_duration: int
    created_at: datetime
    
    class Config:
        from_attributes = True
    
class DoctorCreate(BaseModel):
    email: str
    password: str
    full_name: str
    specialization: Optional[str] = None
    license_number: Optional[str] = None

# Patient User Schemas
class PatientUserCreate(BaseModel):
    email: str
    password: str
    patient_id: str


class PatientUserLogin(BaseModel):
    email: str
    password: str


class PatientUserResponse(BaseModel):
    id: str
    email: str
    patient_id: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


# Patient Message Schemas
class PatientMessageCreate(BaseModel):
    doctor_id: str
    subject: str
    message: str


class PatientMessageResponse(BaseModel):
    id: str
    patient_id: str
    doctor_id: str
    subject: str
    message: str
    sender_type: str
    is_read: bool
    created_at: datetime
    
    class Config:
        from_attributes = True