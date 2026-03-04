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

# Expose ports
EXPOSE 8000
EXPOSE 2575

# Default command: start FastAPI backend
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]