FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy server code
COPY server.py .

# Copy JSON tool definitions into data/
COPY data/ data/

# Run as non-root for security hardening
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Railway injects PORT env var
ENV PORT=8000

EXPOSE 8000

CMD ["python", "server.py"]
