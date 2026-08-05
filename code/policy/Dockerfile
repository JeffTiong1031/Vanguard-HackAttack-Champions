# Build the admin console (Vite → app/static/), then serve API + dashboard from one process.
FROM node:20-slim AS admin-build
WORKDIR /src/admin
COPY admin/package.json admin/package-lock.json ./
RUN npm ci
COPY admin/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
COPY --from=admin-build /src/app/static ./app/static
RUN pip install --no-cache-dir .

# Render sets PORT (commonly 10000). Bind 0.0.0.0 so the health check can reach us.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-access-log"]
