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
COPY ./certs ./certs
COPY logging_config.json ./

# Expose ports
EXPOSE 2575

# Default command: start FastAPI backend using configured bind host/port.
CMD ["sh", "-c", "uvicorn app.api:app --host ${API_BIND_HOST:-0.0.0.0} --port ${API_BIND_PORT:-8000} --log-config logging_config.json"]