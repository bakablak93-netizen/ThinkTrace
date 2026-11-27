# One image = backend API + built frontend, served by FastAPI on one port.

# ---- 1. build the frontend ----
FROM node:22-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# VITE_FX=off builds the frontend without the WebGL background layer
ARG VITE_FX=""
ENV VITE_FX=$VITE_FX
RUN npm run build

# ---- 2. backend + static files ----
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_PATH=/app/data/thinktrace.sqlite3 \
    PORT=10000
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=frontend /app/frontend/dist /app/frontend/dist
RUN mkdir -p /app/data
EXPOSE 10000
# PORT is set by the hosting platform if it uses another port; 10000 otherwise.
CMD ["sh", "-c", "exec uvicorn thinktrace.api:create_app --factory --host 0.0.0.0 --port ${PORT}"]
