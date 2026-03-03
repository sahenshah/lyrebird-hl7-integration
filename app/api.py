from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import logging

logging.basicConfig(level=logging.INFO)

app = FastAPI()


class Patient(BaseModel):
    id: str
    first_name: str
    last_name: str
    dob: str
    gender: str


class MessagePayload(BaseModel):
    message_type: str
    message_control_id: str
    patient: Patient


@app.post("/api/v1/messages")
async def receive_message(payload: MessagePayload):
    """
    Receives transformed HL7 messages as JSON payloads.
    Note: This endpoint is intended for integration with the HL7 listener service.
    """
    logging.info(f"Received payload: {payload.json()}")

    if not payload.patient.id:
        raise HTTPException(status_code=400, detail="Missing patient ID")

    return {"status": "received"}


@app.get("/health")
def health_check():
    """
    Health check endpoint for readiness and monitoring.
    Returns status 'ok' if the API is running.
    """
    return {"status": "ok"}

