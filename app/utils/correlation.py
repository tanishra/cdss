"""
Correlation ID Utilities - Following SOLID Principles
Single Responsibility: Correlation ID management only
"""
import uuid
from typing import Optional
from fastapi import Request


def get_correlation_id(request: Optional[Request]) -> str:
    """
    Get or generate correlation ID for request tracking.
    
    Single Responsibility: Extract or create correlation ID
    
    Args:
        request: FastAPI request object
        
    Returns:
        Correlation ID string
        
    Usage:
        Used for tracking requests across the entire application lifecycle.
        Helps in debugging and audit trail.
    """
    if not request:
        return str(uuid.uuid4())
    
    # Check if correlation ID exists in headers
    correlation_id = request.headers.get("X-Correlation-ID")
    
    if correlation_id:
        return correlation_id
    
    # Generate new correlation ID if not provided
    return str(uuid.uuid4())


def generate_correlation_id() -> str:
    """
    Generate a new correlation ID.
    
    Returns:
        UUID4 string
    """
    return str(uuid.uuid4())


class CorrelationContext:
    """
    Context manager for correlation ID.
    
    Open/Closed Principle: Can extend for different ID generation strategies
    """
    
    def __init__(self, correlation_id: Optional[str] = None):
        self.correlation_id = correlation_id or generate_correlation_id()
    
    def __enter__(self):
        """Enter correlation context."""
        return self.correlation_id
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit correlation context."""
        pass