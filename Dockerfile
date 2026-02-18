FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy server code
COPY server.py .

# Copy JSON tool definitions into data/
COPY data/ data/

# Railway injects PORT env var
ENV PORT=8000

EXPOSE 8000

CMD ["python", "server.py"]
