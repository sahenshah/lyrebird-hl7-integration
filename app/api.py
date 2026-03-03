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
    logging.info(f"Received payload: {payload.json()}")

    if not payload.patient.id:
        raise HTTPException(status_code=400, detail="Missing patient ID")

    return {"status": "received"}