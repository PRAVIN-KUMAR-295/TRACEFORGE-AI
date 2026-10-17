from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from backend.app.models.schemas import InvestigationResult
from backend.app.services.investigation_engine import investigation_engine

router = APIRouter(prefix="/api/investigations", tags=["Investigations"])


class StartInvestigationRequest(BaseModel):
    incident_id: str = "INC-2026-1042"
    custom_description: Optional[str] = None
    enable_agent_mode: Optional[bool] = None


@router.post("/start", response_model=InvestigationResult)
async def start_investigation(req: StartInvestigationRequest):
    """
    Initiates an AI-powered graph investigation for an incident.
    Traverses FalkorDB relationships, separates confirmed facts from hypotheses,
    recalls persistent incident memory, and proposes human-in-the-loop action plans.
    Supports deterministic sequential execution and optional autonomous agent tool loop.
    """
    try:
        result = await investigation_engine.investigate_incident(
            incident_id=req.incident_id,
            custom_query=req.custom_description,
            enable_agent_mode=req.enable_agent_mode,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Investigation failed: {str(e)}")


@router.get("/demo", response_model=InvestigationResult)
async def run_one_click_demo(agent_mode: Optional[bool] = Query(default=None)):
    """
    One-click demo investigation endpoint.
    Performs an end-to-end investigation on the live enterprise cascade failure incident.
    """
    try:
        result = await investigation_engine.investigate_incident(
            incident_id="INC-2026-1042",
            enable_agent_mode=agent_mode,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Demo investigation failed: {str(e)}")


@router.get("", response_model=List[InvestigationResult])
async def list_investigations():
    """
    Returns history of all completed investigations in this session.
    """
    return investigation_engine.list_investigations()


@router.get("/{investigation_id}", response_model=InvestigationResult)
async def get_investigation(investigation_id: str):
    """
    Retrieves full details of an existing investigation.
    """
    inv = investigation_engine.get_investigation(investigation_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return inv
