# Stage 1: Build React Frontend
FROM node:22-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package.json ./package.json
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Unified Full-Stack Python FastAPI + LangGraph + Built Frontend
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY sample_repos /app/sample_repos
COPY backend /app/backend
COPY --from=frontend-builder /frontend/dist /app/frontend/dist

WORKDIR /app/backend
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
