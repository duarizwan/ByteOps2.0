FROM python:3.12-slim

WORKDIR /app

# Install uv for fast dependency installation
RUN pip install uv

# Copy dependency manifest first for better layer caching
COPY pyproject.toml .

# Install production dependencies (skip dev group)
RUN uv pip install --system --no-dev .

# Copy application code
COPY . .

# Expose the port Railway/Render injects via $PORT
EXPOSE 8000

# Start uvicorn — $PORT is set by the platform at runtime
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
