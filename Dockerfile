# Stage 1: Build React frontend
FROM node:22-slim AS frontend
WORKDIR /build
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# Stage 2: Python runtime
FROM python:3.12-slim
WORKDIR /app

COPY requirements-web.txt ./
RUN pip install --no-cache-dir -r requirements-web.txt

COPY api/ ./api/
COPY agent/ ./agent/
COPY shared/ ./shared/
COPY startup.sh ./
RUN chmod +x startup.sh

# Copy built frontend from stage 1
COPY --from=frontend /build/dist/ ./web/dist/

ENV PYTHONUNBUFFERED=1
ENV JOBAGENT_DIR=agent

EXPOSE 8000
CMD ["bash", "startup.sh"]
