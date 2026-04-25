FROM python:3.12-slim

WORKDIR /service

# Install deps first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source (includes app/static/index.html)
COPY app/ ./app/

# Non-root user for security
RUN useradd -m appuser && chown -R appuser /service
USER appuser

ENV PORT=8000
EXPOSE 8000

# Render sets $PORT; locally defaults to 8000.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --loop uvloop --timeout-keep-alive 30"]
