"""DroneDrill AI - Backend API (FastAPI).

Provides core endpoints for training session lifecycle and health checks.
Runs offline with SQLite and local scenario generation.
"""

import uuid
from typing import Any, Dict
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.db import (
    init_db,
    record_session,
    record_cell_seen,
    record_fingerprint,
)
from app.factors import init_split
from app.generator import generate_scenario

# Initialize database schema and condition split
init_db()
init_split()

app = FastAPI(
    title="DroneDrill AI Core",
    description="Offline AI-enabled drone/counter-drone threat simulation trainer API",
    version="1.0.0",
)

# CORS enabled for localhost (various ports)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
        "http://localhost:8080",
        "http://127.0.0.1",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8080",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SessionStartRequest(BaseModel):
    """Payload to start a training session."""
    trainee_id: str = Field(..., description="Unique identifier for the trainee")


@app.get("/health")
def health() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/session/start")
def start_session(request: SessionStartRequest) -> Dict[str, Any]:
    """Start a simulation session for a trainee.
    
    Generates a practice scenario, records the session and cell visit,
    and stores the scenario fingerprint.
    """
    if not request.trainee_id.strip():
        raise HTTPException(status_code=400, detail="trainee_id cannot be empty")

    trainee_id = request.trainee_id.strip()
    session_id = str(uuid.uuid4())

    # Generate scenario (strictly from practice cells)
    scenario = generate_scenario(allow_held_out=False)

    # Persist session and track visited skill cell
    record_session(
        session_id=session_id,
        trainee_id=trainee_id,
        scenario_id=scenario["scenario_id"],
        cell=scenario["cell"],
        difficulty_index=scenario["difficulty_index"],
    )
    record_cell_seen(
        trainee_id=trainee_id,
        cell=scenario["cell"],
    )

    # Store scenario fingerprint
    record_fingerprint(
        fingerprint=scenario["fingerprint"],
        scenario_id=scenario["scenario_id"],
    )

    # Return session information along with scenario details
    return {
        "session_id": session_id,
        "fingerprint": scenario["fingerprint"],
        "scenario_id": scenario["scenario_id"],
        "cell": scenario["cell"],
        "factors": scenario["factors"],
        "objects": scenario["objects"],
        "duration_s": scenario["duration_s"],
        "difficulty_index": scenario["difficulty_index"],
        "scenario": scenario,
    }
