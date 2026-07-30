# Root Dockerfile for unified build
# See docker-compose.yml for multi-service setup
FROM python:3.11-slim AS backend-build
WORKDIR /app
COPY backend/pyproject.toml ./
COPY backend/src ./src
RUN pip install --upgrade pip && pip install -e .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
