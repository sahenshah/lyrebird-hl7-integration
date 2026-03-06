from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging

logger = logging.getLogger("app.api")

app = FastAPI()


class Patient(BaseModel):
    mrn: str
    first_name: str
    last_name: str
    dob: str
    sex: str

class Source(BaseModel):
    sending_app: Optional[str] = None
    sending_facility: Optional[str] = None

class MessagePayload(BaseModel):
    message_type: str
    message_control_id: str
    patient: Patient
    source: Optional[Source] = None

@app.post("/api/v1/messages")
async def receive_message(payload: MessagePayload):
    """
    Receives transformed HL7 messages as JSON payloads.
    Note: This endpoint is intended for integration with the HL7 listener service.
    """
    logger.info(
        f"Received payload: {payload.model_dump_json()}",
        extra={
            "control_id": payload.message_control_id,
            "message_type": payload.message_type,
            "patient_id": payload.patient.mrn
        }
    )

    if not payload.patient.mrn:
        raise HTTPException(status_code=400, detail="Missing patient MRN")

    return {"status": "received"}


@app.get("/health")
def health_check():
    """
    Health check endpoint for readiness and monitoring.
    Returns status 'ok' if the API is running.
    """
    return {"status": "ok"}

