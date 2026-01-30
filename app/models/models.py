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
    
    # Relationships - Open/Closed Principle: Easy to extend without modification
    patients = relationship("Patient", back_populates="doctor", cascade="all, delete-orphan")
    diagnoses = relationship("Diagnosis", back_populates="doctor", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="doctor", cascade="all, delete-orphan")
    
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
    
    # Relationships
    doctor = relationship("Doctor", back_populates="patients")
    diagnoses = relationship("Diagnosis", back_populates="patient", cascade="all, delete-orphan")
    
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
    
    # Performance Metrics
    processing_time_ms = Column(Float)
    llm_model_used = Column(String)
    llm_tokens_used = Column(Integer)
    
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
    
    # Indexes
    __table_args__ = (
        Index('idx_diagnosis_patient', 'patient_id'),
        Index('idx_diagnosis_doctor', 'doctor_id'),
        Index('idx_diagnosis_created', 'created_at'),
        Index('idx_diagnosis_correlation', 'correlation_id'),
    )
    
    def __repr__(self) -> str:
        return f"<Diagnosis(id={self.id}, patient_id={self.patient_id})>"


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