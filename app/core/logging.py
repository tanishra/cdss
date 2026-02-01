"""
Logging Configuration
"""
import logging
import sys
from pathlib import Path
import structlog

from app.core.config import settings


def setup_logging() -> None:
    """Configure structured logging."""
    log_path = Path(settings.LOG_FILE)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
    root_logger.addHandler(handler)


def get_logger(name: str) -> structlog.BoundLogger:
    """Get structured logger."""
    return structlog.get_logger(name)


class AuditLogger:
    """Audit logger for clinical decisions."""
    
    def __init__(self):
        self.logger = get_logger("audit")
    
    def log_diagnosis(self, patient_id: str, doctor_id: str, diagnoses: list, 
                     confidence_scores: list, duration_ms: float, correlation_id: str) -> None:
        """Log diagnosis event."""
        self.logger.info(
            "diagnosis_generated",
            event_type="clinical_decision",
            patient_id=patient_id,
            doctor_id=doctor_id,
            diagnoses=diagnoses,
            confidence_scores=confidence_scores,
            duration_ms=duration_ms,
            correlation_id=correlation_id,
        )
    
    def log_patient_access(self, patient_id: str, doctor_id: str, 
                          action: str, correlation_id: str) -> None:
        """Log patient data access."""
        self.logger.info(
            "patient_access",
            event_type="data_access",
            patient_id=patient_id,
            doctor_id=doctor_id,
            action=action,
            correlation_id=correlation_id,
        )
    
    def log_authentication(self, doctor_id: str, action: str, success: bool, 
                      ip_address: str, correlation_id: str) -> None:
          """Log authentication event."""
          self.logger.info(
              "authentication",
              event_type="security",
              doctor_id=doctor_id,
              action=action,
              success=success,
              ip_address=ip_address,
              correlation_id=correlation_id,
        )


audit_logger = AuditLogger()