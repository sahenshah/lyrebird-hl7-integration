import logging
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.core.config import DOWNSTREAM_API_URL, DOWNSTREAM_CA_BUNDLE
import httpx 

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

    verify_tls: str | bool = True
    if DOWNSTREAM_CA_BUNDLE:
        if os.path.exists(DOWNSTREAM_CA_BUNDLE):
            verify_tls = DOWNSTREAM_CA_BUNDLE
        else:
            logger.error(f"DOWNSTREAM_CA_BUNDLE not found: {DOWNSTREAM_CA_BUNDLE}")
            raise HTTPException(status_code=502, detail="Downstream TLS configuration error")

    try:
        async with httpx.AsyncClient(verify=verify_tls, timeout=10.0) as client:
            response = await client.post(DOWNSTREAM_API_URL, json=payload.model_dump())
            response.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to post to downstream API: {e}")
        raise HTTPException(status_code=502, detail="Downstream API call failed")

    return {"status": "received"}


@app.get("/health")
def health_check():
    """
    Health check endpoint for readiness and monitoring.
    Returns status 'ok' if the API is running.
    """
    return {"status": "ok"}

