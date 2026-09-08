# Main API Service

FastAPI service for authentication, bot management, scenario management, and chat runtime.

## Running Locally

```bash
# Sync dependencies with uv
uv sync

# Run development server
uv run uvicorn app.main:app --reload --port 8000
```

## Useful URLs

- **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Admin Dashboard**: [http://localhost:8000/admin](http://localhost:8000/admin)
- **Health Check**: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)
- **Database Health**: [http://localhost:8000/api/v1/health/db](http://localhost:8000/api/v1/health/db)
