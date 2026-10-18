"""DroneDrill AI - Backend API (FastAPI).

Provides core endpoints for training session lifecycle and health checks.
Runs offline with SQLite and local scenario generation.
"""

import uuid
from typing import Any, Dict, List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.db import (
    init_db,
    record_session,
    record_cell_seen,
    record_fingerprint,
    record_event,
    get_session,
    update_session_score,
)
from app.factors import init_split
from app.generator import generate_scenario
from app.scoring import score_session

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


class SessionResultRequest(BaseModel):
    """Payload to submit trainee events and evaluate a completed session."""
    session_id: str = Field(..., description="Active session ID to evaluate")
    events: List[Dict[str, Any]] = Field(default_factory=list, description="List of object interaction events")
    false_alarms: int = Field(0, description="Number of false alarms triggered")


@app.get("/health")
def health() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/session/start")
def start_session(request: SessionStartRequest) -> Dict[str, Any]:
    """Start a simulation session for a trainee.
    
    Generates a practice scenario, records the session and cell visit,
    stores the full scenario JSON for reloading, and stores the scenario fingerprint.
    """
    if not request.trainee_id.strip():
        raise HTTPException(status_code=400, detail="trainee_id cannot be empty")

    trainee_id = request.trainee_id.strip()
    session_id = str(uuid.uuid4())

    # Generate scenario (strictly from practice cells)
    scenario = generate_scenario(allow_held_out=False)

    # Persist session with full scenario JSON and track visited skill cell
    record_session(
        session_id=session_id,
        trainee_id=trainee_id,
        scenario_id=scenario["scenario_id"],
        cell=scenario["cell"],
        difficulty_index=scenario["difficulty_index"],
        scenario_json=scenario,
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
        "noise_windows": scenario.get("noise_windows", 3),
        "difficulty_index": scenario["difficulty_index"],
        "scenario": scenario,
    }


@app.post("/session/result")
def submit_session_result(request: SessionResultRequest) -> Dict[str, Any]:
    """Evaluate trainee performance and store results for the completed session."""
    session = get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    scenario = session.get("scenario")
    if not scenario:
        raise HTTPException(status_code=400, detail="Scenario data not found for session")

    # Store individual interaction events in events table
    for ev in request.events:
        record_event(
            session_id=request.session_id,
            event_type="object_assessment",
            payload=ev,
        )

    if request.false_alarms > 0:
        record_event(
            session_id=request.session_id,
            event_type="false_alarm_count",
            payload={"count": request.false_alarms},
        )

    # Calculate multi-dimensional score
    scores = score_session(
        scenario=scenario,
        events=request.events,
        false_alarms=request.false_alarms,
    )

    # Persist overall score to the session record
    update_session_score(request.session_id, scores["overall"])

    return scores
