# Production Dockerfile for AURA-NSE Pro
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for ultra-fast deterministic dependency management
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# Copy requirements and install
COPY pyproject.toml .
RUN uv pip install --system \
    fastapi \
    uvicorn \
    pydantic \
    pydantic-settings \
    sqlalchemy \
    alembic \
    apscheduler \
    pandas \
    numpy \
    yfinance \
    scikit-learn \
    lightgbm \
    shap \
    httpx \
    tenacity \
    cryptography \
    pyyaml \
    google-genai

# Copy application code and built frontend
COPY . .

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
