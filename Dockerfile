# ----------------------------
# Lyrebird HL7 Integration Dockerfile
# ----------------------------

# Use official Python 3.10 slim image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy and install dependencies first (minimizes image size)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY ./app ./app
COPY .env ./
COPY logging_config.json ./
COPY cert.pem ./
COPY key.pem ./

# Expose ports
EXPOSE 8000
EXPOSE 2575

# Default command: start FastAPI backend over HTTPS using self-signed certificate with valid JSON output.
CMD ["uvicorn", "app.api:app", "--host", "localhost", "--port", "8000", "--ssl-keyfile", "key.pem", "--ssl-certfile", "cert.pem", "--log-config", "logging_config.json"]