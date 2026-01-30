"""
API Tests Module - Following SOLID Principles
Single Responsibility: Test API endpoints
"""
import pytest
import asyncio
from typing import AsyncGenerator
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.main import app
from app.core.database import Base, get_db
from app.core.config import settings
from dotenv import load_dotenv
import os

load_dotenv()

# Test database URL
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

# Create test engine
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


# ============================================================================
# FIXTURES - Dependency Inversion Principle
# ============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Create test database session.
    
    Single Responsibility: Provide test database
    """
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with TestSessionLocal() as session:
        yield session
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Create test client.
    
    Dependency Inversion: Override database dependency
    """
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest.fixture
async def authenticated_client(client: AsyncClient) -> AsyncClient:
    """
    Create authenticated test client.
    
    Single Responsibility: Provide authenticated client
    """
    # Register doctor
    doctor_data = {
        "email": "test@example.com",
        "password": "TestPassword123",
        "full_name": "Dr. Test Doctor",
        "specialization": "Internal Medicine",
    }
    
    await client.post(f"{settings.API_PREFIX}/auth/register", json=doctor_data)
    
    # Login to get token
    login_response = await client.post(
        f"{settings.API_PREFIX}/auth/login",
        json={"email": doctor_data["email"], "password": doctor_data["password"]},
    )
    
    token = login_response.json()["access_token"]
    
    # Set authorization header
    client.headers.update({"Authorization": f"Bearer {token}"})
    
    return client


# ============================================================================
# HEALTH CHECK TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Test health check endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    
    data = response.json()
    assert "status" in data
    assert "version" in data
    assert data["version"] == settings.APP_VERSION


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """Test root endpoint."""
    response = await client.get("/")
    assert response.status_code == 200
    
    data = response.json()
    assert data["name"] == settings.APP_NAME
    assert "version" in data
    assert data["status"] == "running"


# ============================================================================
# AUTHENTICATION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_doctor_registration_success(client: AsyncClient):
    """Test successful doctor registration."""
    doctor_data = {
        "email": "newdoctor@example.com",
        "password": "SecurePassword123",
        "full_name": "Dr. New Doctor",
        "specialization": "Cardiology",
        "license_number": "MD12345",
        "phone": "+1234567890",
    }
    
    response = await client.post(f"{settings.API_PREFIX}/auth/register", json=doctor_data)
    
    assert response.status_code == 201
    data = response.json()
    
    assert data["email"] == doctor_data["email"]
    assert data["full_name"] == doctor_data["full_name"]
    assert data["specialization"] == doctor_data["specialization"]
    assert "id" in data
    assert "hashed_password" not in data  # Password should not be exposed
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_doctor_registration_duplicate_email(client: AsyncClient):
    """Test registration with duplicate email."""
    doctor_data = {
        "email": "duplicate@example.com",
        "password": "TestPassword123",
        "full_name": "Dr. First",
    }
    
    # First registration
    await client.post(f"{settings.API_PREFIX}/auth/register", json=doctor_data)
    
    # Second registration with same email
    response = await client.post(f"{settings.API_PREFIX}/auth/register", json=doctor_data)
    
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_doctor_registration_weak_password(client: AsyncClient):
    """Test registration with weak password."""
    doctor_data = {
        "email": "weak@example.com",
        "password": "weak",
        "full_name": "Dr. Weak",
    }
    
    response = await client.post(f"{settings.API_PREFIX}/auth/register", json=doctor_data)
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_doctor_login_success(client: AsyncClient):
    """Test successful login."""
    # Register
    doctor_data = {
        "email": "login@example.com",
        "password": "LoginPassword123",
        "full_name": "Dr. Login",
    }
    
    await client.post(f"{settings.API_PREFIX}/auth/register", json=doctor_data)
    
    # Login
    login_data = {
        "email": doctor_data["email"],
        "password": doctor_data["password"],
    }
    
    response = await client.post(f"{settings.API_PREFIX}/auth/login", json=login_data)
    
    assert response.status_code == 200
    data = response.json()
    
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "expires_in" in data


@pytest.mark.asyncio
async def test_doctor_login_invalid_credentials(client: AsyncClient):
    """Test login with invalid credentials."""
    login_data = {
        "email": "nonexistent@example.com",
        "password": "WrongPassword123",
    }
    
    response = await client.post(f"{settings.API_PREFIX}/auth/login", json=login_data)
    
    assert response.status_code == 401
    assert "incorrect" in response.json()["detail"].lower()


# ============================================================================
# PATIENT TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_create_patient_success(authenticated_client: AsyncClient):
    """Test successful patient creation."""
    patient_data = {
        "mrn": "MRN001",
        "full_name": "John Doe",
        "date_of_birth": "1980-05-15",
        "gender": "Male",
        "blood_group": "O+",
        "phone": "+1234567890",
        "allergies": ["Penicillin"],
        "chronic_conditions": ["Hypertension"],
        "smoking_status": "Never",
    }
    
    response = await authenticated_client.post(
        f"{settings.API_PREFIX}/patients/",
        json=patient_data,
    )
    
    assert response.status_code == 201
    data = response.json()
    
    assert data["mrn"] == patient_data["mrn"]
    assert data["full_name"] == patient_data["full_name"]
    assert data["gender"] == patient_data["gender"]
    assert "id" in data


@pytest.mark.asyncio
async def test_create_patient_unauthorized(client: AsyncClient):
    """Test patient creation without authentication."""
    patient_data = {
        "mrn": "MRN002",
        "full_name": "Jane Doe",
        "date_of_birth": "1990-01-01",
        "gender": "Female",
    }
    
    response = await client.post(f"{settings.API_PREFIX}/patients/", json=patient_data)
    
    assert response.status_code == 403  # No authentication


@pytest.mark.asyncio
async def test_get_patient_success(authenticated_client: AsyncClient):
    """Test successful patient retrieval."""
    # Create patient
    patient_data = {
        "mrn": "MRN003",
        "full_name": "Test Patient",
        "date_of_birth": "1985-03-20",
        "gender": "Male",
    }
    
    create_response = await authenticated_client.post(
        f"{settings.API_PREFIX}/patients/",
        json=patient_data,
    )
    
    patient_id = create_response.json()["id"]
    
    # Get patient
    response = await authenticated_client.get(f"{settings.API_PREFIX}/patients/{patient_id}")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["id"] == patient_id
    assert data["mrn"] == patient_data["mrn"]


@pytest.mark.asyncio
async def test_get_patient_not_found(authenticated_client: AsyncClient):
    """Test patient retrieval with invalid ID."""
    response = await authenticated_client.get(
        f"{settings.API_PREFIX}/patients/invalid-id-12345"
    )
    
    assert response.status_code == 404


# ============================================================================
# DIAGNOSIS TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_diagnosis_validation(authenticated_client: AsyncClient):
    """Test diagnosis request validation."""
    # Invalid request - missing required fields
    invalid_request = {
        "patient_id": "some-id",
        "chief_complaint": "Test",
        # Missing symptoms
    }
    
    response = await authenticated_client.post(
        f"{settings.API_PREFIX}/diagnosis/analyze",
        json=invalid_request,
    )
    
    assert response.status_code == 422  # Validation error


# Note: Full diagnosis test requires Anthropic API key
# This would be tested in integration tests


# ============================================================================
# CORRELATION ID TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_correlation_id_header(client: AsyncClient):
    """Test correlation ID is returned in response."""
    correlation_id = "test-correlation-id-123"
    
    response = await client.get(
        "/health",
        headers={"X-Correlation-ID": correlation_id},
    )
    
    assert response.headers.get("X-Correlation-ID") == correlation_id


@pytest.mark.asyncio
async def test_correlation_id_generated(client: AsyncClient):
    """Test correlation ID is generated if not provided."""
    response = await client.get("/health")
    
    assert "X-Correlation-ID" in response.headers
    assert len(response.headers["X-Correlation-ID"]) > 0