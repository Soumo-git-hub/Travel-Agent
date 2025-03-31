from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uvicorn
from api_config import api_settings
from app import generate_recommendations, generate_conversational_response

app = FastAPI(
    title="Travel Agent API",
    description="API for the AI Travel Agent",
    version=api_settings.API_VERSION
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=api_settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class TravelRequest(BaseModel):
    destination: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, str]]] = None
    travel_info: Optional[Dict[str, Any]] = None

# Dependencies
async def verify_api_key(x_api_key: str = Header(None)):
    if api_settings.API_KEY and x_api_key != api_settings.API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return x_api_key

# Routes
@app.get("/")
async def root():
    return {"message": "Welcome to Travel Agent API"}

@app.post("/api/recommendations")
async def get_recommendations(
    request: TravelRequest,
    api_key: str = Depends(verify_api_key)
):
    try:
        recommendations = generate_recommendations(
            destination=request.destination,
            start_date=request.start_date,
            end_date=request.end_date,
            preferences=request.preferences
        )
        return recommendations
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
async def chat(
    request: ChatRequest,
    api_key: str = Depends(verify_api_key)
):
    try:
        response = generate_conversational_response(
            user_input=request.message,
            travel_info=request.travel_info,
            history=request.history
        )
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=api_settings.DEBUG
    ) 