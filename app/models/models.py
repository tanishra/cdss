"""
Database Models Module - Following SOLID Principles
"""
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, ForeignKey, Boolean, JSON, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.core.database import Base


def generate_uuid() -> str:
    """Generate unique identifier."""
    return str(uuid.uuid4())


class Doctor(Base):
    """
    Doctor/User Model
    Single Responsibility: Represents doctor entity only
    """
    __tablename__ = "doctors"
    
    # Primary Key
    id = Column(String, primary_key=True, default=generate_uuid)
    
    # Authentication
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    
    # Profile
    full_name = Column(String, nullable=False)
    specialization = Column(String)
    license_number = Column(String, unique=True)
    phone = Column(String)
    
    # Status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True))

    organization_id = Column(String, ForeignKey("organizations.id"), nullable=True)
    department_id = Column(String, ForeignKey("departments.id"), nullable=True)
    role_id = Column(String, ForeignKey("roles.id"), nullable=True)
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    # Relationships - Open/Closed Principle: Easy to extend without modification
    diagnoses = relationship("Diagnosis", back_populates="doctor", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="doctor", cascade="all, delete-orphan")
    organization = relationship("Organization", back_populates="doctors")
    department_rel = relationship("Department", foreign_keys=[department_id], back_populates="doctors")
    role = relationship("Role")
    patients = relationship("Patient", foreign_keys="Patient.doctor_id",back_populates="doctor", cascade="all, delete-orphan")
    assigned_patients = relationship("Patient", foreign_keys="Patient.assigned_doctor_id",back_populates="assigned_doctor", cascade="all, delete-orphan")

    phone = Column(String, nullable=True)
    bio = Column(Text, nullable=True)
    hospital = Column(String, nullable=True)
    department = Column(String, nullable=True)
    years_experience = Column(Integer, nullable=True)
    profile_picture = Column(String, nullable=True)
    
    # Settings
    email_notifications = Column(Boolean, default=True)
    appointment_reminders = Column(Boolean, default=True)
    two_factor_enabled = Column(Boolean, default=False)
    default_appointment_duration = Column(Integer, default=30)
    
    def __repr__(self) -> str:
        return f"<Doctor(id={self.id}, email={self.email})>"


class Patient(Base):
    """
    Patient Model
    Single Responsibility: Patient data management
    """
    __tablename__ = "patients"
    
    # Primary Key
    id = Column(String, primary_key=True, default=generate_uuid)
    doctor_id = Column(String, ForeignKey("doctors.id"), nullable=False)
    
    # Identifiers
    mrn = Column(String, unique=True, nullable=False, index=True)  # Medical Record Number
    
    # Demographics
    full_name = Column(String, nullable=False)
    date_of_birth = Column(DateTime, nullable=False)
    gender = Column(String)
    blood_group = Column(String)
    
    # Contact
    phone = Column(String)
    email = Column(String)
    address = Column(Text)
    
    # Medical History - JSON for flexibility (Open/Closed Principle)
    allergies = Column(JSON)
    chronic_conditions = Column(JSON)
    medications = Column(JSON)
    family_history = Column(JSON)
    surgical_history = Column(JSON)
    
    # Lifestyle
    smoking_status = Column(String)
    alcohol_consumption = Column(String)
    
    # Metadata
    is_active = Column(Boolean, default=True)
    notes = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    organization_id = Column(String, ForeignKey("organizations.id"), nullable=True)
    assigned_doctor_id = Column(String, ForeignKey("doctors.id"), nullable=True)
    
    # Relationships
    doctor = relationship("Doctor", foreign_keys=[doctor_id],back_populates="patients")
    diagnoses = relationship("Diagnosis", back_populates="patient", cascade="all, delete-orphan")
    organization = relationship("Organization", back_populates="patients")
    assigned_doctor = relationship("Doctor", foreign_keys=[assigned_doctor_id], back_populates="assigned_patients")
    
    # Indexes - Performance optimization
    __table_args__ = (
        Index('idx_patient_doctor', 'doctor_id'),
        Index('idx_patient_created', 'created_at'),
    )
    
    def __repr__(self) -> str:
        return f"<Patient(id={self.id}, mrn={self.mrn})>"


class Diagnosis(Base):
    """
    Diagnosis Model
    Single Responsibility: Clinical decision record
    Liskov Substitution: Can be extended for specific diagnosis types
    """
    __tablename__ = "diagnoses"
    
    # Primary Keys
    id = Column(String, primary_key=True, default=generate_uuid)
    patient_id = Column(String, ForeignKey("patients.id"), nullable=False)
    doctor_id = Column(String, ForeignKey("doctors.id"), nullable=False)
    
    # Tracking
    correlation_id = Column(String, nullable=False, index=True)
    
    # Input Data
    chief_complaint = Column(Text, nullable=False)
    symptoms = Column(JSON, nullable=False)
    symptom_duration = Column(String)
    symptom_severity = Column(String)
    
    # Vital Signs
    temperature = Column(Float)
    blood_pressure_systolic = Column(Integer)
    blood_pressure_diastolic = Column(Integer)
    heart_rate = Column(Integer)
    respiratory_rate = Column(Integer)
    oxygen_saturation = Column(Float)
    
    # Additional Data
    lab_results = Column(JSON)
    imaging_findings = Column(JSON)
    
    # AI Output - Interface Segregation: Separate concerns
    differential_diagnoses = Column(JSON, nullable=False)
    clinical_reasoning = Column(Text)
    missing_information = Column(JSON)
    red_flags = Column(JSON)
    
    # Recommendations
    recommended_tests = Column(JSON)
    recommended_treatments = Column(JSON)
    follow_up_instructions = Column(Text)

    # RAG-specific fields
    evidence_used = Column(JSON) 
    guidelines_applied = Column(JSON)  
    citation_count = Column(Integer, default=0)  
    
    # Performance Metrics
    processing_time_ms = Column(Float)
    llm_model_used = Column(String)
    llm_tokens_used = Column(Integer)
    rag_enabled = Column(Boolean, default=False)
    
    # Doctor Feedback - Dependency Inversion: Depends on abstraction
    doctor_feedback = Column(JSON)
    
    # Status
    status = Column(String, default="active")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    patient = relationship("Patient", back_populates="diagnoses")
    doctor = relationship("Doctor", back_populates="diagnoses")
    citations = relationship("Citation", back_populates="diagnosis", cascade="all, delete-orphan")  
    feedbacks = relationship("DoctorFeedback", back_populates="diagnosis", cascade="all, delete-orphan")

    lab_results_raw = Column(JSON)  # Raw uploaded lab data
    lab_results_parsed = Column(JSON)  # Parsed and interpreted
    lab_abnormalities = Column(JSON)  # Flagged abnormal values

    treatments = relationship("Treatment", back_populates="diagnosis")
    
    # Indexes
    __table_args__ = (
        Index('idx_diagnosis_patient', 'patient_id'),
        Index('idx_diagnosis_doctor', 'doctor_id'),
        Index('idx_diagnosis_created', 'created_at'),
        Index('idx_diagnosis_correlation', 'correlation_id'),
    )
    
    def __repr__(self) -> str:
        return f"<Diagnosis(id={self.id}, patient_id={self.patient_id})>"
    
class Citation(Base):
    """
    Citation Model - Stores medical literature references
    """
    __tablename__ = "citations"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    diagnosis_id = Column(String, ForeignKey("diagnoses.id"), nullable=False)
    
    # PubMed Article Info
    pubmed_id = Column(String, index=True)  # PMID
    title = Column(Text, nullable=False)
    authors = Column(Text)
    journal = Column(String)
    publication_year = Column(Integer)
    doi = Column(String)
    
    # Citation Details
    citation_text = Column(Text)  
    relevance_score = Column(Float)  
    evidence_type = Column(String)  
    
    # Content
    abstract = Column(Text)
    url = Column(String)
    
    # Association
    diagnosis_name = Column(String)  
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    diagnosis = relationship("Diagnosis", back_populates="citations")
    
    # Indexes
    __table_args__ = (
        Index('idx_citation_diagnosis', 'diagnosis_id'),
        Index('idx_citation_pubmed', 'pubmed_id'),
    )
    
    def __repr__(self) -> str:
        return f"<Citation(id={self.id}, pubmed_id={self.pubmed_id})>"
    

class DoctorFeedback(Base):
    """
    NEW: Doctor Feedback Model - Stores doctor's assessment of diagnosis
    """
    __tablename__ = "doctor_feedbacks"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    diagnosis_id = Column(String, ForeignKey("diagnoses.id"), nullable=False)
    doctor_id = Column(String, ForeignKey("doctors.id"), nullable=False)
    
    # Feedback Data
    correct_diagnosis = Column(String, nullable=False)  
    was_in_top_5 = Column(Boolean, nullable=False)
    actual_rank = Column(Integer)  
    
    # Detailed Feedback
    missing_symptoms = Column(JSON)  
    incorrect_symptoms = Column(JSON)  
    missing_tests = Column(JSON)  
    
    # Quality Ratings (1-5)
    accuracy_rating = Column(Integer)
    reasoning_quality = Column(Integer)
    recommendations_quality = Column(Integer)
    overall_satisfaction = Column(Integer)
    
    # Comments
    feedback_notes = Column(Text)
    would_use_again = Column(Boolean)
    
    # Treatment Outcome (optional, follow-up)
    treatment_given = Column(String)
    patient_outcome = Column(String)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    diagnosis = relationship("Diagnosis", back_populates="feedbacks")
    doctor = relationship("Doctor")
    
    # Indexes
    __table_args__ = (
        Index('idx_feedback_diagnosis', 'diagnosis_id'),
        Index('idx_feedback_doctor', 'doctor_id'),
        Index('idx_feedback_created', 'created_at'),
    )
    
    def __repr__(self) -> str:
        return f"<DoctorFeedback(id={self.id}, diagnosis_id={self.diagnosis_id})>"

class Treatment(Base):
    """Treatment records for diagnoses."""
    __tablename__ = "treatments"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    diagnosis_id = Column(String, ForeignKey("diagnoses.id"), nullable=False)
    patient_id = Column(String, ForeignKey("patients.id"), nullable=False)
    doctor_id = Column(String, ForeignKey("doctors.id"), nullable=False)
    
    # Treatment details
    treatment_type = Column(String, nullable=False)  # medication, procedure, therapy, lifestyle
    medication_name = Column(String)  # For medications
    dosage = Column(String)
    frequency = Column(String)
    route = Column(String)  # oral, IV, topical, etc.
    duration = Column(String)  # "7 days", "2 weeks", etc.
    
    # Additional details
    instructions = Column(Text)
    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime)
    
    # Outcome tracking
    status = Column(String, default="active")  # active, completed, discontinued
    effectiveness = Column(String)  # effective, partially_effective, ineffective, unknown
    side_effects = Column(JSON)  # List of side effects
    adherence = Column(String)  # excellent, good, fair, poor
    
    # Interaction warnings
    has_interactions = Column(Boolean, default=False)
    interaction_warnings = Column(JSON)
    
    # Notes
    notes = Column(Text)
    discontinuation_reason = Column(String)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    diagnosis = relationship("Diagnosis", back_populates="treatments")
    patient = relationship("Patient")
    doctor = relationship("Doctor")


class Prescription(Base):
    """Prescription generation for treatments."""
    __tablename__ = "prescriptions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String, ForeignKey("patients.id"), nullable=False)
    doctor_id = Column(String, ForeignKey("doctors.id"), nullable=False)
    diagnosis_id = Column(String, ForeignKey("diagnoses.id"))
    
    # Prescription details
    prescription_number = Column(String, unique=True)
    date_issued = Column(DateTime, default=datetime.utcnow)
    valid_until = Column(DateTime)
    
    # Medications (JSON array)
    medications = Column(JSON, nullable=False)  # List of medication objects
    
    # Additional info
    diagnosis_summary = Column(Text)
    special_instructions = Column(Text)
    refills_allowed = Column(Integer, default=0)
    
    # Status
    status = Column(String, default="active")  # active, filled, expired, cancelled
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    patient = relationship("Patient")
    doctor = relationship("Doctor")

class AuditLog(Base):
    """
    Audit Log Model
    Single Responsibility: Audit trail only
    """
    __tablename__ = "audit_logs"
    
    # Primary Key
    id = Column(String, primary_key=True, default=generate_uuid)
    
    # Event Classification
    event_type = Column(String, nullable=False, index=True)
    action = Column(String, nullable=False)
    
    # Actor
    doctor_id = Column(String, ForeignKey("doctors.id"), nullable=True)
    ip_address = Column(String)
    user_agent = Column(String)
    
    # Target
    resource_type = Column(String)
    resource_id = Column(String)
    
    # Details
    details = Column(JSON)
    correlation_id = Column(String, index=True)
    
    # Status
    success = Column(Boolean, default=True)
    error_message = Column(Text)
    
    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    doctor = relationship("Doctor", back_populates="audit_logs")
    
    # Indexes
    __table_args__ = (
        Index('idx_audit_event_type', 'event_type'),
        Index('idx_audit_doctor', 'doctor_id'),
        Index('idx_audit_created', 'created_at'),
    )
    
    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, event_type={self.event_type})>"
    
class ClinicalNote(Base):
    """Clinical notes per patient visit."""
    __tablename__ = "clinical_notes"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String, ForeignKey("patients.id"), nullable=False)
    doctor_id = Column(String, ForeignKey("doctors.id"), nullable=False)
    diagnosis_id = Column(String, ForeignKey("diagnoses.id"), nullable=True)
    
    # Note content
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    note_type = Column(String, default="general")  # general, follow_up, procedure, referral
    is_private = Column(Boolean, default=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    patient = relationship("Patient")
    doctor = relationship("Doctor")


class VitalRecord(Base):
    """Vitals tracking over time."""
    __tablename__ = "vital_records"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String, ForeignKey("patients.id"), nullable=False)
    doctor_id = Column(String, ForeignKey("doctors.id"), nullable=False)
    diagnosis_id = Column(String, ForeignKey("diagnoses.id"), nullable=True)
    
    # Vital signs
    temperature = Column(Float, nullable=True)
    blood_pressure_systolic = Column(Integer, nullable=True)
    blood_pressure_diastolic = Column(Integer, nullable=True)
    heart_rate = Column(Integer, nullable=True)
    respiratory_rate = Column(Integer, nullable=True)
    oxygen_saturation = Column(Float, nullable=True)
    weight = Column(Float, nullable=True)
    height = Column(Float, nullable=True)
    bmi = Column(Float, nullable=True)
    blood_glucose = Column(Float, nullable=True)
    
    # Notes
    notes = Column(Text, nullable=True)
    recorded_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    patient = relationship("Patient")
    doctor = relationship("Doctor")


class Appointment(Base):
    """Appointment scheduler."""
    __tablename__ = "appointments"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String, ForeignKey("patients.id"), nullable=False)
    doctor_id = Column(String, ForeignKey("doctors.id"), nullable=False)
    diagnosis_id = Column(String, ForeignKey("diagnoses.id"), nullable=True)
    
    # Appointment details
    title = Column(String, nullable=False)
    appointment_type = Column(String, default="follow_up")  # follow_up, consultation, procedure, checkup
    scheduled_at = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, default=30)
    
    # Status
    status = Column(String, default="scheduled")  # scheduled, completed, cancelled, no_show
    
    # Notes
    notes = Column(Text, nullable=True)
    reminder_sent = Column(Boolean, default=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    patient = relationship("Patient")
    doctor = relationship("Doctor")


class Organization(Base):
    """Hospital/Clinic organization."""
    __tablename__ = "organizations"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    org_type = Column(String, default="clinic")  # clinic, hospital, private_practice
    address = Column(Text)
    phone = Column(String)
    email = Column(String)
    website = Column(String)
    registration_number = Column(String)
    
    # Settings
    logo_url = Column(String)
    timezone = Column(String, default="UTC")
    is_active = Column(Boolean, default=True)
    
    # Subscription (for future billing)
    plan = Column(String, default="free")  # free, basic, pro, enterprise
    max_doctors = Column(Integer, default=5)
    max_patients = Column(Integer, default=100)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    doctors = relationship("Doctor", back_populates="organization")
    patients = relationship("Patient", back_populates="organization")
    departments = relationship("Department", back_populates="organization")


class Department(Base):
    """Departments within organization."""
    __tablename__ = "departments"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    name = Column(String, nullable=False)  # Cardiology, Emergency, ICU, etc.
    description = Column(Text)
    head_doctor_id = Column(String, ForeignKey("doctors.id"), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    organization = relationship("Organization", back_populates="departments")
    doctors = relationship("Doctor", foreign_keys="Doctor.department_id", back_populates="department_rel")


class Role(Base):
    """User roles for access control."""
    __tablename__ = "roles"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, unique=True)  # admin, doctor, nurse, receptionist
    description = Column(Text)
    permissions = Column(JSON)  # {"can_edit_patients": true, "can_delete_diagnoses": false}
    
    created_at = Column(DateTime, default=datetime.utcnow)


class PatientUser(Base):
    """Patient login accounts - separate from Patient records."""
    __tablename__ = "patient_users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String, ForeignKey("patients.id"), nullable=False, unique=True)
    
    # Authentication
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime)
    
    # Relationship
    patient = relationship("Patient", backref="user_account")
    
    def __repr__(self) -> str:
        return f"<PatientUser(id={self.id}, email={self.email})>"


class PatientMessage(Base):
    """Messages between patients and doctors."""
    __tablename__ = "patient_messages"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String, ForeignKey("patients.id"), nullable=False)
    doctor_id = Column(String, ForeignKey("doctors.id"), nullable=False)
    
    # Message
    subject = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    sender_type = Column(String, nullable=False)  # patient, doctor
    
    # Status
    is_read = Column(Boolean, default=False)
    parent_message_id = Column(String, ForeignKey("patient_messages.id"), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    patient = relationship("Patient")
    doctor = relationship("Doctor")