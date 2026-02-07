# Clinical Decision Support System

A production-grade AI-powered clinical decision support system that assists doctors in generating differential diagnoses using OpenAI.

## Features

- **AI-Powered Differential Diagnosis** - Generate top 5 most likely diagnoses with confidence scores
- **Patient Management** - Complete patient records with medical history tracking
- **Clinical Reasoning** - Detailed explanations, supporting evidence, and recommendations
- **Graceful Degradation** - Works with symptoms alone, better with vital signs and lab results
- **JWT Authentication** - Secure doctor authentication and authorization
- **Audit Trails** - Complete logging of all clinical decisions for compliance
- **Rate Limiting** - Redis-backed rate limiting to prevent abuse
- **Production-Ready** - Comprehensive error handling, logging, and monitoring

## Tech Stack

- **Backend**: FastAPI (Python 3.11)
- **Database**: PostgreSQL 16
- **Cache**: Redis 7
- **AI**: OpenAI GPT-4o-mini
- **Authentication**: JWT + Bcrypt
- **ORM**: SQLAlchemy (Async)
- **Validation**: Pydantic

## Architecture
```
FastAPI → Services → OpenAI
    ↓
PostgreSQL + Redis
```

**SOLID Principles Applied Throughout**

## Prerequisites

- Python 3.11+
- PostgreSQL 16+
- Redis 7+
- OpenAI API Key

## Quick Start

### 1. Clone and Setup
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Setup Database
```bash
# Create PostgreSQL database
psql -U postgres
CREATE DATABASE clinical_db;
\q
```

### 3. Configure Environment
```bash
# Copy environment template
cp .env.example .env

# Edit .env and add your Anthropic API key
```

Required configuration in `.env`:
```bash
OPENAI_API_KEY=your-api-key-here
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/clinical_db
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-secret-key-min-32-chars
```

### 4. Start Services
```bash
# Start PostgreSQL (if not running)
brew services start postgresql@16  # macOS
sudo systemctl start postgresql     # Linux

# Start Redis (if not running)
brew services start redis           # macOS
sudo systemctl start redis-server   # Linux

# Run application
uvicorn app.main:app --reload --port 8000
```

### 5. Access Application

- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **ReDoc**: http://localhost:8000/redoc

## API Endpoints

### Authentication

- `POST /api/v1/auth/register` - Register new doctor
- `POST /api/v1/auth/login` - Login and get JWT token

### Patients

- `POST /api/v1/patients/` - Create patient record
- `GET /api/v1/patients/{id}` - Get patient details

### Diagnosis

- `POST /api/v1/diagnosis/analyze` - Generate AI-powered differential diagnosis

### Health

- `GET /health` - Application health status

## Usage Example

### 1. Register Doctor
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "doctor@hospital.com",
    "password": "SecurePass123",
    "full_name": "Dr. Jane Smith",
    "specialization": "Internal Medicine"
  }'
```

### 2. Login
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "doctor@hospital.com",
    "password": "SecurePass123"
  }'
```

### 3. Create Patient
```bash
curl -X POST http://localhost:8000/api/v1/patients/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "mrn": "MRN001",
    "full_name": "John Doe",
    "date_of_birth": "1980-05-15",
    "gender": "Male",
    "allergies": ["Penicillin"]
  }'
```

### 4. Generate Diagnosis
```bash
curl -X POST http://localhost:8000/api/v1/diagnosis/analyze \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "PATIENT_ID",
    "chief_complaint": "Persistent cough and fever",
    "symptoms": [
      {"name": "Cough", "severity": "Moderate", "duration": "3 days"},
      {"name": "Fever", "severity": "Moderate"}
    ],
    "vital_signs": {
      "temperature": 38.5,
      "heart_rate": 95
    }
  }'
```

**Response includes:**
- Top 5 differential diagnoses
- Confidence scores (0-1)
- ICD-10 codes
- Clinical reasoning
- Supporting evidence
- Recommended tests
- Treatment suggestions
- Red flags/warnings

## Configuration

Key environment variables:
```bash
# Application
APP_NAME="Clinical Decision Support System"
DEBUG=True
ENVIRONMENT=development

# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/clinical_db
DATABASE_POOL_SIZE=20

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your-secret-key-min-32-chars
ACCESS_TOKEN_EXPIRE_MINUTES=30

# AI
OPENAI_API_KEY=your-api-key
OPENAI_MODEL=gpt-4o-mini

# Rate Limiting
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_PERIOD=60
```

## Development
```bash
# Activate virtual environment
source venv/bin/activate

# Run with auto-reload
uvicorn app.main:app --reload

# Check code style
black app/
ruff check app/

# View logs
tail -f logs/app.log
```

## Monitoring

- Health check endpoint: `/health`
- Database connection monitoring
- Redis connection monitoring
- Request/response timing
- Error rate tracking

## Troubleshooting

### Database connection error
```bash
# Check PostgreSQL is running
psql -U postgres -c "SELECT 1"

# Verify DATABASE_URL in .env
```

### Redis connection error
```bash
# Check Redis is running
redis-cli ping  # Should return PONG
```

### Import errors
```bash
# Ensure virtual environment is activated
# Reinstall dependencies
pip install -r requirements.txt
```

### Port already in use
```bash
# Use different port
uvicorn app.main:app --reload --port 8001
```

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Follow SOLID principles and existing code style
4. Add tests for new features
5. Ensure all tests pass (`pytest`)
6. Update documentation as needed
7. Commit changes (`git commit -m 'Add amazing feature'`)
8. Push to branch (`git push origin feature/amazing-feature`)
9. Open a Pull Request
