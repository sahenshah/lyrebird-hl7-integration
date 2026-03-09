from fastapi import FastAPI, Request

app = FastAPI()

@app.post("/receive")
async def receive(request: Request):
    data = await request.json()
    print("Received downstream payload:", data)
    return {"status": "ok"}